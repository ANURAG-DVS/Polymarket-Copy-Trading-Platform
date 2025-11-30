"""
Polymarket Copy Trading Platform - Streamlit Dashboard
====================================================

A comprehensive dashboard for monitoring and managing the Polymarket Copy Trading Platform.
Runs on port 8500 by default.

Features:
- Real-time trading analytics and performance metrics
- Portfolio overview and risk management
- System health monitoring
- User management and subscription tracking
- Market data visualization
- API endpoint monitoring
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import psycopg2
import redis
import asyncio

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="Polymarket Copy Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #ff6b6b;
    }
    .success-card {
        background-color: #d4edda;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #28a745;
    }
    .warning-card {
        background-color: #fff3cd;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #ffc107;
    }
    .sidebar-header {
        font-size: 24px;
        font-weight: bold;
        color: #ff6b6b;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "database": os.getenv("POSTGRES_DB", "polymarket_copy_dev"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "dev_password_123")
}

# Redis Configuration
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": 0
}

class DashboardApp:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.db_config = DB_CONFIG
        self.redis_config = REDIS_CONFIG

    def get_backend_health(self):
        """Check backend API health"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            return response.json() if response.status_code == 200 else {"status": "unhealthy"}
        except:
            return {"status": "unreachable"}

    def get_database_connection(self):
        """Test database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.close()
            return {"status": "healthy", "message": "Connected"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}

    def get_redis_connection(self):
        """Test Redis connection"""
        try:
            r = redis.Redis(**self.redis_config)
            r.ping()
            return {"status": "healthy", "message": "Connected"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}

    def get_system_metrics(self):
        """Get comprehensive system metrics"""
        return {
            "backend": self.get_backend_health(),
            "database": self.get_database_connection(),
            "redis": self.get_redis_connection(),
            "timestamp": datetime.now().isoformat()
        }

    def create_main_dashboard(self):
        """Main dashboard layout"""
        st.title("📈 Polymarket Copy Trading Platform Dashboard")

        # System Health Overview
        st.header("🔍 System Health Overview")

        col1, col2, col3, col4 = st.columns(4)

        metrics = self.get_system_metrics()

        with col1:
            backend_status = metrics["backend"].get("status", "unknown")
            status_color = "🟢" if backend_status == "healthy" else "🔴"
            st.metric("Backend API", f"{status_color} {backend_status.title()}")

        with col2:
            db_status = metrics["database"].get("status", "unknown")
            status_color = "🟢" if db_status == "healthy" else "🔴"
            st.metric("Database", f"{status_color} {db_status.title()}")

        with col3:
            redis_status = metrics["redis"].get("status", "unknown")
            status_color = "🟢" if redis_status == "healthy" else "🔴"
            st.metric("Redis Cache", f"{status_color} {redis_status.title()}")

        with col4:
            st.metric("Last Updated", datetime.now().strftime("%H:%M:%S"))

        # Trading Performance Section
        st.header("📊 Trading Performance")

        # Sample trading data (replace with real data from API)
        trading_data = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=30, freq='D'),
            'pnl': [100, 150, 200, 180, 250, 300, 280, 350, 400, 380,
                   450, 500, 480, 550, 600, 580, 650, 700, 680, 750,
                   800, 780, 850, 900, 880, 950, 1000, 980, 1050, 1100],
            'volume': [1000, 1200, 1100, 1300, 1250, 1400, 1350, 1500, 1450, 1600,
                      1550, 1700, 1650, 1800, 1750, 1900, 1850, 2000, 1950, 2100,
                      2050, 2200, 2150, 2300, 2250, 2400, 2350, 2500, 2450, 2600]
        })

        col1, col2 = st.columns(2)

        with col1:
            fig = px.line(trading_data, x='date', y='pnl',
                         title='Portfolio P&L Over Time',
                         labels={'pnl': 'Profit & Loss ($)', 'date': 'Date'})
            fig.update_traces(line_color='#ff6b6b')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(trading_data, x='date', y='volume',
                        title='Trading Volume Over Time',
                        labels={'volume': 'Volume ($)', 'date': 'Date'})
            fig.update_traces(marker_color='#4ecdc4')
            st.plotly_chart(fig, use_container_width=True)

        # Market Data Section
        st.header("🌍 Market Data & Analytics")

        # Sample market data
        market_data = pd.DataFrame({
            'market': ['BTC/USD', 'ETH/USD', 'ADA/USD', 'DOT/USD', 'SOL/USD'],
            'price': [45000, 2800, 0.45, 8.50, 95.20],
            'change_24h': [2.5, -1.2, 5.8, 3.1, -0.8],
            'volume': [1500000, 800000, 200000, 150000, 300000]
        })

        # Color code for price changes
        market_data['color'] = market_data['change_24h'].apply(
            lambda x: 'green' if x > 0 else 'red'
        )

        fig = go.Figure(data=[
            go.Bar(
                x=market_data['market'],
                y=market_data['volume'],
                marker_color=market_data['color'],
                text=market_data['change_24h'].apply(lambda x: f"{x:+.1f}%"),
                textposition='auto',
            )
        ])

        fig.update_layout(
            title="Market Volume & 24h Change",
            xaxis_title="Markets",
            yaxis_title="24h Volume ($)",
        )

        st.plotly_chart(fig, use_container_width=True)

        # Real-time Updates
        st.header("🔄 Real-time Updates")

        placeholder = st.empty()

        # Auto-refresh every 30 seconds
        if st.button("🔄 Refresh Data"):
            with placeholder.container():
                st.success("Data refreshed successfully!")
                st.json(metrics)

        # Footer
        st.markdown("---")
        st.markdown("*Polymarket Copy Trading Platform Dashboard - Running on port 8500*")

def main():
    """Main application entry point"""
    dashboard = DashboardApp()

    # Sidebar navigation
    st.sidebar.markdown('<div class="sidebar-header">📈 Dashboard</div>', unsafe_allow_html=True)

    pages = {
        "🏠 Overview": "main",
        "📊 Trading Analytics": "trading",
        "💰 Portfolio": "portfolio",
        "👥 Users": "users",
        "⚙️ System Health": "system",
        "🤖 Telegram Bot": "telegram"
    }

    selected_page = st.sidebar.selectbox("Navigate to:", list(pages.keys()))

    # Main content based on selection
    if pages[selected_page] == "main":
        dashboard.create_main_dashboard()

    elif pages[selected_page] == "trading":
        st.title("📊 Trading Analytics")
        st.info("Trading analytics page - Coming soon!")

    elif pages[selected_page] == "portfolio":
        st.title("💰 Portfolio Management")
        st.info("Portfolio management page - Coming soon!")

    elif pages[selected_page] == "users":
        st.title("👥 User Management")
        st.info("User management page - Coming soon!")

    elif pages[selected_page] == "system":
        st.title("⚙️ System Health Monitoring")

        col1, col2, col3 = st.columns(3)

        metrics = dashboard.get_system_metrics()

        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("Backend API")
            st.write(f"Status: {metrics['backend'].get('status', 'unknown').title()}")
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("Database")
            st.write(f"Status: {metrics['database'].get('status', 'unknown').title()}")
            st.markdown('</div>', unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("Redis Cache")
            st.write(f"Status: {metrics['redis'].get('status', 'unknown').title()}")
            st.markdown('</div>', unsafe_allow_html=True)

        # Detailed system information
        st.subheader("System Details")
        st.json(metrics)

    elif pages[selected_page] == "telegram":
        st.title("🤖 Telegram Bot Status")
        st.info("Telegram bot monitoring - Coming soon!")

    # Auto-refresh toggle
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)

    if auto_refresh:
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
