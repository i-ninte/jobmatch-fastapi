from sqlalchemy import create_engine, text

# Database connection URL
DATABASE_URL = "postgresql://root:oNPgKgQdPhWWXOJCXRWJ9EcOfwRa6DzZ@dpg-csf0p8rtq21c738hv89g-a.oregon-postgres.render.com:5432/jobmatch_w82w"

# Create a SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Function to print existing tables in the database
def print_tables():
    try:
        # Connect to the database
        with engine.connect() as connection:
            # Check the connected database name
            db_info = connection.execute(text("SELECT current_database();"))
            print("Connected to database:", db_info.fetchone()[0])

            # Retrieve and print all table names
            tables = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
            print("Existing tables:")
            for table in tables:
                print(table[0])
    except Exception as e:
        print(f"Error connecting to the database: {e}")

# Execute the function to print tables
if __name__ == "__main__":
    print_tables()
