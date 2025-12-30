import gradio as gr
import requests
import os
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATION & ASSETS ---

# Supabase Credentials
SUPABASE_URL = "https://uwwfzmzjtzravvagdvjm.supabase.co"
SUPABASE_KEY = "sb_publishable_r9Zz7tB_52rRiP6OSqiMsA_5qeo9qKV"

# GitHub Asset URLs
GITHUB_BASE = "https://raw.githubusercontent.com/arvindkathpalreload-bit/Mishti/refs/heads/main"
LOGO_URL = "https://github.com/arvindkathpalreload-bit/Mishti/blob/main/mishTee_logo.png?raw=true"
CSS_URL = f"{GITHUB_BASE}/style.css"

def get_db_connection():
    """Helper to establish connection to Supabase."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_brand_assets():
    """
    Downloads the Logo and CSS from GitHub.
    Returns the CSS string and the local path to the logo image.
    """
    print("Initializing MishTee-Magic App...")
    
    # Fetch CSS
    try:
        css_response = requests.get(CSS_URL)
        if css_response.status_code == 200:
            app_css = css_response.text
        else:
            print("Warning: Could not fetch CSS. Using fallback.")
            app_css = ""
    except Exception as e:
        print(f"Error fetching CSS: {e}")
        app_css = ""

    # Fetch Logo
    logo_path = "mishTee_logo.png"
    try:
        if not os.path.exists(logo_path):
            logo_response = requests.get(LOGO_URL)
            if logo_response.status_code == 200:
                with open(logo_path, "wb") as f:
                    f.write(logo_response.content)
            else:
                print("Warning: Could not fetch Logo.")
    except Exception as e:
        print(f"Error fetching Logo: {e}")
    
    return app_css, logo_path

# Initialize Assets
mishtee_css, logo_file = fetch_brand_assets()


# --- 2. LOGIC FUNCTIONS (Backend) ---

def process_login(phone_input):
    """
    Orchestrator function triggered by the Login Button.
    1. Gets Customer Greeting & History.
    2. Gets Trending Products (regardless of user, but triggered here for UX flow).
    Returns: [Greeting Text, History DataFrame, Trending DataFrame]
    """
    if not phone_input:
        return "Please enter a valid mobile number.", pd.DataFrame(), pd.DataFrame()

    greeting, df_history = get_customer_history(phone_input)
    df_trending = get_trending_products()
    
    return greeting, df_history, df_trending

def get_customer_history(phone_input):
    """Fetches customer name and order history."""
    supabase = get_db_connection()
    
    # A. FETCH CUSTOMER DETAILS
    try:
        cust_response = supabase.table("customers")\
            .select("full_name")\
            .eq("phone", phone_input)\
            .execute()
        
        if cust_response.data:
            customer_name = cust_response.data[0]['full_name']
            greeting = f"## Namaste, {customer_name} ji! Great to see you again."
        else:
            return "## Namaste! It looks like you are new here.", pd.DataFrame()
            
    except Exception as e:
        return f"Error connecting to Database: {str(e)}", pd.DataFrame()

    # B. FETCH ORDER HISTORY
    try:
        orders_response = supabase.table("orders")\
            .select("*")\
            .eq("cust_phone", phone_input)\
            .order("order_date", desc=True)\
            .execute()
        
        if not orders_response.data:
            empty_df = pd.DataFrame(columns=["Date", "Item ID", "Qty (kg)", "Value (₹)", "Status"])
            return greeting, empty_df

        df_orders = pd.DataFrame(orders_response.data)
        
        # Select and Rename columns for clarity
        # Using .get() ensures we don't crash if a column is missing in schema updates
        data = {
            "Date": df_orders.get("order_date"),
            "Sweet ID": df_orders.get("product_id"),
            "Qty (kg)": df_orders.get("qty_kg"),
            "Total (₹)": df_orders.get("order_value_inr"),
            "Status": df_orders.get("status")
        }
        df_display = pd.DataFrame(data)
        
        return greeting, df_display

    except Exception as e:
        return f"Error retrieving orders: {str(e)}", pd.DataFrame()

def get_trending_products():
    """Fetches top 4 best selling products."""
    supabase = get_db_connection()
    
    try:
        # A. FETCH DATA
        orders_response = supabase.table("orders").select("product_id, qty_kg").execute()
        products_response = supabase.table("products").select("item_id, sweet_name, variant_type, price_per_kg").execute()
        
        if not orders_response.data or not products_response.data:
            return pd.DataFrame(columns=["No Data Available"])

        # B. PROCESS
        df_orders = pd.DataFrame(orders_response.data)
        df_products = pd.DataFrame(products_response.data)
        
        # Group by Product ID and Sum Quantity
        df_trending = df_orders.groupby("product_id")['qty_kg'].sum().reset_index()
        
        # Sort Top 4
        df_trending = df_trending.sort_values(by='qty_kg', ascending=False).head(4)
        
        # Merge details
        df_final = pd.merge(
            df_trending, 
            df_products, 
            left_on='product_id', 
            right_on='item_id', 
            how='left'
        )
        
        # Format
        df_final['Artisanal Selection'] = df_final['sweet_name'] + " (" + df_final['variant_type'] + ")"
        df_final['Price / Kg (₹)'] = df_final['price_per_kg']
        df_final['Total Kgs Sold'] = df_final['qty_kg']
        
        return df_final[['Artisanal Selection', 'Price / Kg (₹)', 'Total Kgs Sold']]

    except Exception as e:
        print(f"Error generating trending list: {e}")
        return pd.DataFrame(columns=["Error Loading Trending"])


# --- 3. UI LAYOUT (Gradio) ---

with gr.Blocks(css=mishtee_css, title="MishTee-Magic") as demo:
    
    # --- HEADER SECTION ---
    with gr.Row(elem_id="header-row"):
        with gr.Column(scale=1): pass
        with gr.Column(scale=2, elem_id="logo-container"):
            if os.path.exists(logo_file):
                gr.Image(value=logo_file, show_label=False, container=False, show_download_button=False, height=120)
            else:
                gr.Markdown("# MishTee-Magic")
            
            gr.Markdown(
                "<h3 style='text-align: center; font-style: italic; color: #C06C5C; margin-top: 10px;'>"
                "Rooted in Earth. Wrapped in Gold.<br>"
                "<span style='font-size: 0.8em; color: #666;'>[ Purity and Health ]</span></h3>"
            )
        with gr.Column(scale=1): pass

    # --- LOGIN SECTION ---
    with gr.Row():
        with gr.Column(scale=1): pass
        with gr.Column(scale=2):
            phone_inp = gr.Textbox(
                placeholder="Enter Mobile Number (e.g., 9998887776)", 
                label="Customer Login", 
                max_lines=1
            )
            login_btn = gr.Button("ENTER THE MAGIC", variant="primary")
            
            # Dynamic Greeting Area
            greeting_output = gr.Markdown(value="", elem_id="greeting-text")
        with gr.Column(scale=1): pass

    # --- MAIN CONTENT (Tabs) ---
    with gr.Tabs():
        
        # TAB 1: ORDER HISTORY
        with gr.TabItem("My Order History"):
            history_output = gr.Dataframe(
                headers=["Date", "Sweet ID", "Qty (kg)", "Total (₹)", "Status"],
                label="Your Past Indulgences",
                interactive=False
            )

        # TAB 2: TRENDING
        with gr.TabItem("Trending Today"):
            trending_output = gr.Dataframe(
                headers=["Artisanal Selection", "Price / Kg (₹)", "Total Kgs Sold"],
                label="Curated Favorites",
                interactive=False
            )

    # --- EVENTS ---
    # When Login is clicked, update Greeting, History, and Trending tables
    login_btn.click(
        fn=process_login,
        inputs=[phone_inp],
        outputs=[greeting_output, history_output, trending_output]
    )

# --- 4. LAUNCH ---
if __name__ == "__main__":
    demo.launch()
