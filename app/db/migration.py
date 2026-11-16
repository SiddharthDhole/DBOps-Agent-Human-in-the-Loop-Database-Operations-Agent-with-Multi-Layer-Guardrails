import os
import psycopg2
from psycopg2 import sql


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pass@1234")
DB_NAME = "dbops_demo"


def create_database():
    """Create the database if it doesn't already exist."""

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres",
    )

    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (DB_NAME,),
            )

            exists = cursor.fetchone()

            if not exists:
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(
                        sql.Identifier(DB_NAME)
                    )
                )
                print(f"Database '{DB_NAME}' created.")
            else:
                print(f"Database '{DB_NAME}' already exists.")

    finally:
        conn.close()


def create_tables():
    """Create application tables."""

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )

    try:
        with conn:
            with conn.cursor() as cursor:

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS customers (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        email VARCHAR(150) UNIQUE NOT NULL,
                        country VARCHAR(50),
                        status VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        category VARCHAR(50),
                        price DECIMAL(10, 2) NOT NULL,
                        stock INTEGER DEFAULT 0
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id SERIAL PRIMARY KEY,
                        customer_id INTEGER REFERENCES customers(id),
                        product_id INTEGER REFERENCES products(id),
                        quantity INTEGER NOT NULL,
                        total_amount DECIMAL(10, 2) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id SERIAL PRIMARY KEY,
                        order_id INTEGER REFERENCES orders(id),
                        amount DECIMAL(10, 2) NOT NULL,
                        payment_method VARCHAR(30),
                        status VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

        print("Tables created successfully.")

    finally:
        conn.close()


def insert_dummy_data():
    """Insert demo data."""

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )

    try:
        with conn:
            with conn.cursor() as cursor:

                # Customers
                cursor.execute("""
                    INSERT INTO customers
                        (name, email, country, status)
                    VALUES
                        ('Rahul Sharma', 'rahul@example.com', 'India', 'active'),
                        ('Priya Patil', 'priya@example.com', 'India', 'active'),
                        ('John Smith', 'john@example.com', 'USA', 'active'),
                        ('David Wilson', 'david@example.com', 'UK', 'inactive'),
                        ('Sneha Kulkarni', 'sneha@example.com', 'India', 'active')
                    ON CONFLICT (email) DO NOTHING;
                """)

                # Products
                cursor.execute("""
                    INSERT INTO products
                        (name, category, price, stock)
                    VALUES
                        ('Laptop', 'Electronics', 75000, 15),
                        ('Mouse', 'Electronics', 1500, 100),
                        ('Keyboard', 'Electronics', 3000, 50),
                        ('Monitor', 'Electronics', 25000, 8),
                        ('Headphones', 'Audio', 5000, 25)
                    ON CONFLICT DO NOTHING;
                """)

                # Orders
                cursor.execute("""
                    INSERT INTO orders
                        (customer_id, product_id, quantity, total_amount, status)
                    SELECT * FROM (
                        VALUES
                            (1, 1, 1, 75000::DECIMAL, 'completed'),
                            (1, 2, 2, 3000::DECIMAL, 'completed'),
                            (2, 3, 1, 3000::DECIMAL, 'completed'),
                            (3, 4, 2, 50000::DECIMAL, 'completed'),
                            (5, 5, 1, 5000::DECIMAL, 'completed'),
                            (2, 1, 1, 75000::DECIMAL, 'pending')
                    ) AS data(
                        customer_id,
                        product_id,
                        quantity,
                        total_amount,
                        status
                    )
                    WHERE NOT EXISTS (
                        SELECT 1 FROM orders
                    );
                """)

                # Payments
                cursor.execute("""
                    INSERT INTO payments
                        (order_id, amount, payment_method, status)
                    SELECT * FROM (
                        VALUES
                            (1, 75000::DECIMAL, 'UPI', 'success'),
                            (2, 3000::DECIMAL, 'CARD', 'success'),
                            (3, 3000::DECIMAL, 'UPI', 'success'),
                            (4, 50000::DECIMAL, 'CARD', 'success'),
                            (5, 5000::DECIMAL, 'UPI', 'success'),
                            (6, 75000::DECIMAL, 'CARD', 'pending')
                    ) AS data(
                        order_id,
                        amount,
                        payment_method,
                        status
                    )
                    WHERE NOT EXISTS (
                        SELECT 1 FROM payments
                    );
                """)

        print("Dummy data inserted successfully.")

    finally:
        conn.close()


def main():
    print("Starting DB initialization...")

    create_database()
    create_tables()
    insert_dummy_data()

    print("\nDatabase setup completed successfully.")


if __name__ == "__main__":
    main()