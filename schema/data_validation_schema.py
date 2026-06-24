try:
    
    from pydantic import BaseModel, field_validator,ConfigDict
except Exception:
   
    from pydantic import BaseModel
    from pydantic import validator as field_validator,ConfigDict
import re
from enum import Enum
from typing import List,Literal
from uuid import UUID

