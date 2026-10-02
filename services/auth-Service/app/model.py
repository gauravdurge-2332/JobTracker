from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__="user"

    id:Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email:Mapped[str] = mapped_column(String(35) ,unique=True , index=True , nullable=False)
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
