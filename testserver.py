from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://postgres@localhost:5432/postgres")
with engine.connect() as conn:
    result = conn.execute(text("SELECT 1"))
    print(result.fetchone())
