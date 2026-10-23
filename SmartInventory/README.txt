SMART INVENTORY & ORDER MANAGEMENT SYSTEM

Requirements:
- Python 3.10 or newer recommended
- Flask (installed using requirements.txt)

Run on Windows (VS Code terminal):
1. Open the SmartInventory folder in VS Code.
2. Create and activate a virtual environment (optional but recommended):
   py -m venv .venv
   .venv\Scripts\activate
3. Install Flask:
   pip install -r requirements.txt
4. Start the app:
   python main.py
5. Open the local address shown in the terminal, usually:
   http://127.0.0.1:5000

FEATURES INCLUDED
- Product catalog with ID, name, category, price, available stock, and reorder point
- Add products
- Restock incoming products
- Low-stock warnings
- Checkout with quantity validation, percentage discount, and tax
- Receipt page with print / Save as PDF option
- SQLite database persistence (inventory.db is created automatically)
- Sales history and recent receipts
- Best-selling items report
- Total inventory value and sales summary
- Export sales report to CSV

NOTES
- The app uses only Python (Flask + built-in sqlite3/csv), HTML, and CSS.
- The receipt's Print / Save as PDF button uses a small browser print action in HTML; no separate JavaScript file is used.
- This is a local educational prototype. For deployment, set a strong secret key and turn off Flask debug mode.
