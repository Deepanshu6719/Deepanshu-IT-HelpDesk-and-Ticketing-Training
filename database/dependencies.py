
from database.connection import SessionLocal

def get_db():
    db=SessionLocal()  #this line creates session using SessionLocal()
    try:
        yield db #provides this session to a endpoint/request
    finally:
        db.close()