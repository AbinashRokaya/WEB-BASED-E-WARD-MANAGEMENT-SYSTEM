"""
One-off backfill: generate the missing receipt for every payment
that actually completed but has no TaxReceiptModel row yet.

Run this as a plain script (`python backfill_tax_receipts.py`), NOT
inside an async/event-loop context — issue_tax_receipt() uses
Playwright's sync API, which requires no event loop running in the
current thread. A bare script satisfies that.

Why the extra filters below (not just assessment.status == PAID):
The receipt artifact (pdf_path/qr_path/data_hash) now lives in its own
TaxReceiptModel row, one-to-one with TaxPaymentModel — mirroring
CertificateModel's split from BirthRegistrationModel. But
TaxAssessmentModel.payments is a one-to-many: a citizen can have more
than one TaxPaymentModel row per assessment if, say, a Khalti attempt
was abandoned or failed before a later attempt succeeded. Filtering on
assessment.status == PAID alone matches every payment row on that
assessment with no receipt — including the abandoned/failed one, which
should never get one. So we also require the payment row itself to be
the one that actually completed:
  - CASH/other manual methods are always final as recorded, or
  - KHALTI rows where Khalti confirmed gateway_status == "Completed"
and, as a last cross-check, that amount_paid actually covers what was
due — the same condition record_tax_payment used to flip PAID in the
first place. (Same rule as TaxAssessmentModel.receipt uses.)

Usage:
    cd backend/
    python backfill_tax_receipts.py
"""
from database.db import SessionLocal

# FIX: UserModel (and others) declare relationship() targets as plain
# strings, e.g. relationship("DeathRegistrationModel"). SQLAlchemy only
# resolves those names lazily, when mappers first get configured — and
# it can only find classes whose module has actually been imported
# somewhere in this process. Your main.py works because it imports
# every model module up front; this standalone script previously only
# imported model.tax_model, so any OTHER model class referenced by a
# relationship() string (DeathRegistrationModel, MarriageModel, etc.)
# was never registered, and configuring TaxPaymentModel's mappers blew
# up trying to resolve it via UserModel's relationships.
#
# Fix: import every .py under model/ before touching the DB, so all
# classes are registered regardless of how many registration types
# exist or get added later.
import importlib
import pkgutil
import model as _model_pkg

for _, module_name, _ in pkgutil.iter_modules(_model_pkg.__path__):
    importlib.import_module(f"model.{module_name}")

from model.tax_model import TaxPaymentModel, TaxAssessmentModel, TaxReceiptModel
from enums.tax_enums import TaxAssessmentStatus, TaxPaymentMethod
from services.tax_receipt_service import issue_tax_receipt


def main():
    db = SessionLocal()
    try:
        broken = (
            db.query(TaxPaymentModel)
            .join(TaxAssessmentModel, TaxPaymentModel.assessment_id == TaxAssessmentModel.id)
            .outerjoin(TaxReceiptModel, TaxReceiptModel.payment_id == TaxPaymentModel.id)
            .filter(
                TaxAssessmentModel.status == TaxAssessmentStatus.PAID,
                TaxReceiptModel.id.is_(None),
                TaxPaymentModel.amount_paid >= TaxAssessmentModel.total_due,
                (
                    (TaxPaymentModel.method != TaxPaymentMethod.KHALTI)
                    | (TaxPaymentModel.gateway_status == "Completed")
                ),
            )
            .all()
        )

        print(f"Found {len(broken)} completed payment(s) with no receipt.")

        fixed, failed = 0, 0
        for payment in broken:
            try:
                issue_tax_receipt(db, payment)
                print(f"  fixed  {payment.id} (receipt {payment.receipt_no})")
                fixed += 1
            except Exception as e:
                print(f"  FAILED {payment.id} (receipt {payment.receipt_no}): {e}")
                failed += 1

        print(f"\nDone. {fixed} fixed, {failed} still failing.")
    finally:
        db.close()


if __name__ == "__main__":
    main()