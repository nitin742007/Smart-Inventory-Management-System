from flask import Flask, render_template, request, redirect, url_for, flash, Response, abort
import sqlite3
import csv
import io
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-development-secret"
BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "inventory.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,   
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                min_stock INTEGER NOT NULL CHECK(min_stock >= 0)
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TEXT NOT NULL,
                subtotal REAL NOT NULL,
                discount_percent REAL NOT NULL,
                discount_amount REAL NOT NULL,
                tax_percent REAL NOT NULL,
                tax_amount REAL NOT NULL,
                total REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY(sale_id) REFERENCES sales(id),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
            );
        """)
        count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO products (name, category, price, stock, min_stock) VALUES (?, ?, ?, ?, ?)",
                [
                    ("Notebook", "Stationery", 50, 100, 20),
                    ("Blue Pen", "Stationery", 10, 15, 50),
                    ("Campus T-Shirt", "Clothing", 300, 5, 10),
                ],
            )


@app.route("/")
def index():
    with get_db() as db:
        products = db.execute("SELECT * FROM products ORDER BY name COLLATE NOCASE").fetchall()
        total_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        total_units = db.execute("SELECT COALESCE(SUM(stock), 0) FROM products").fetchone()[0]
        low_stock_count = db.execute("SELECT COUNT(*) FROM products WHERE stock < min_stock").fetchone()[0]
        inventory_value = db.execute("SELECT COALESCE(SUM(stock * price), 0) FROM products").fetchone()[0]
        sales_summary = db.execute("SELECT COUNT(*) AS count, COALESCE(SUM(total), 0) AS total FROM sales").fetchone()
        recent_sales = db.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 8").fetchall()
        best_sellers = db.execute("""
            SELECT product_name, SUM(quantity) AS units_sold, SUM(line_total) AS revenue
            FROM sale_items GROUP BY product_name ORDER BY units_sold DESC, revenue DESC LIMIT 5
        """).fetchall()
    return render_template(
        "index.html", products=products, total_products=total_products,
        total_units=total_units, low_stock_count=low_stock_count,
        inventory_value=inventory_value, sales_summary=sales_summary,
        recent_sales=recent_sales, best_sellers=best_sellers
    )


@app.route("/add_product", methods=["POST"])
def add_product():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    try:
        price = float(request.form.get("price", ""))
        stock = int(request.form.get("stock", ""))
        min_stock = int(request.form.get("min_stock", ""))
        if not name or not category or price < 0 or stock < 0 or min_stock < 0:
            raise ValueError
    except ValueError:
        flash("Enter a product name, category, valid price, and non-negative stock values.", "error")
        return redirect(url_for("index"))
    with get_db() as db:
        db.execute("INSERT INTO products (name, category, price, stock, min_stock) VALUES (?, ?, ?, ?, ?)",
                   (name, category, price, stock, min_stock))
    flash(f"{name} was added to the product catalog.", "success")
    return redirect(url_for("index"))


@app.route("/restock", methods=["POST"])
def restock():
    try:
        product_id = int(request.form.get("product_id", ""))
        quantity = int(request.form.get("quantity", ""))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        flash("Choose a product and enter a restock quantity greater than zero.", "error")
        return redirect(url_for("index"))
    with get_db() as db:
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            flash("Product not found.", "error")
        else:
            db.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))
            flash(f"Restocked {quantity} units of {product['name']}.", "success")
    return redirect(url_for("index"))


@app.route("/checkout", methods=["POST"])
def checkout():
    try:
        product_id = int(request.form.get("product_id", ""))
        quantity = int(request.form.get("quantity", ""))
        discount_percent = float(request.form.get("discount_percent", "0"))
        tax_percent = float(request.form.get("tax_percent", "0"))
        if quantity <= 0 or not (0 <= discount_percent <= 100) or not (0 <= tax_percent <= 100):
            raise ValueError
    except ValueError:
        flash("Enter a valid product, quantity, discount (0–100%), and tax (0–100%).", "error")
        return redirect(url_for("index"))

    with get_db() as db:
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            flash("Please select a valid product.", "error")
            return redirect(url_for("index"))
        if product["stock"] < quantity:
            flash(f"Not enough stock for {product['name']}. Only {product['stock']} units are available.", "error")
            return redirect(url_for("index"))

        subtotal = round(product["price"] * quantity, 2)
        discount_amount = round(subtotal * discount_percent / 100, 2)
        taxable_amount = subtotal - discount_amount
        tax_amount = round(taxable_amount * tax_percent / 100, 2)
        total = round(taxable_amount + tax_amount, 2)
        sale_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = db.execute("""
            INSERT INTO sales (sale_date, subtotal, discount_percent, discount_amount, tax_percent, tax_amount, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sale_date, subtotal, discount_percent, discount_amount, tax_percent, tax_amount, total))
        sale_id = cursor.lastrowid
        db.execute("INSERT INTO sale_items (sale_id, product_id, product_name, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?)",
                   (sale_id, product_id, product["name"], quantity, product["price"], subtotal))
        db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
    return redirect(url_for("receipt", sale_id=sale_id))


@app.route("/receipt/<int:sale_id>")
def receipt(sale_id):
    with get_db() as db:
        sale = db.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if sale is None:
            abort(404)
        items = db.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
    return render_template("receipt.html", sale=sale, items=items)


@app.route("/export/sales.csv")
def export_sales():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Sale ID", "Date", "Subtotal", "Discount %", "Discount Amount", "Tax %", "Tax Amount", "Total"])
    with get_db() as db:
        rows = db.execute("SELECT * FROM sales ORDER BY id DESC").fetchall()
        for sale in rows:
            writer.writerow([sale["id"], sale["sale_date"], sale["subtotal"], sale["discount_percent"],
                             sale["discount_amount"], sale["tax_percent"], sale["tax_amount"], sale["total"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=sales_report.csv"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
