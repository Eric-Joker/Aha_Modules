from sqlalchemy import BigInteger, Column, String

from core.database import dbBase


class Status(dbBase):
    __tablename__ = "latest_msg"

    platform = Column(String(16), primary_key=True)
    group_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), primary_key=True)
    message = Column(BigInteger, default=None)
