from database.db import Base
import model.user_model
import model.address_model
import model.ward_model
import model.birth_registration_model
import model.child_model
import model.parent_model
import model.informant_model
import model.nominee_model
import model.document_model
import model.certificate_model
import model.workflow_log_model

print(Base.metadata.tables.keys())
print(Base.metadata.tables.keys())