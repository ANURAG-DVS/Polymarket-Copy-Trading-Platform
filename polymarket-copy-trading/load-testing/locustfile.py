import asyncio
import httpx
from locust import HttpUser, task, between, events
from locust import LoadTestShape
import random

class PolymarketUser(HttpUser):
    """Simulated user for load testing"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts"""
        # Register and login
        self.register_user()
        self.login()
    
    def register_user(self):
        """Register a new user"""
        user_id = random.randint(1, 1000000)
        response = self.client.post("/api/v1/auth/register", json={
            "email": f"test{user_id}@example.com",
            "username": f"testuser{user_id}",
            "password": "TestPassword123!"
        })
        
        if response.status_code == 201:
            self.user_data = response.json()
    
    def login(self):
        """Login user"""
        if hasattr(self, 'user_data'):
            response = self.client.post("/api/v1/auth/login", json={
                "email": self.user_data['email'],
                "password": "TestPassword123!"
            })
            
            if response.status_code == 200:
                self.token = response.json()['access_token']
                self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def view_leaderboard(self):
        """View trader leaderboard (most common action)"""
        self.client.get("/api/v1/traders/leaderboard?limit=20")
    
    @task(2)
    def view_trader_details(self):
        """View specific trader details"""
        trader_id = random.randint(1, 100)
        self.client.get(f"/api/v1/traders/{trader_id}")
    
    @task(2)
    def view_dashboard(self):
        """View user dashboard"""
        if hasattr(self, 'headers'):
            self.client.get("/api/v1/dashboard", headers=self.headers)
    
    @task(1)
    def create_copy_relationship(self):
        """Create a copy relationship"""
        if hasattr(self, 'headers'):
            trader_id = random.randint(1, 100)
            self.client.post("/api/v1/copy-relationships", headers=self.headers, json={
                "trader_id": trader_id,
                "copy_percentage": random.uniform(1, 10),
                "max_investment_usd": random.uniform(50, 500)
            })
    
    @task(1)
    def health_check(self):
        """Health check endpoint"""
        self.client.get("/health")

class StepLoadShape(LoadTestShape):
    """
    A step load shape
    
    Keyword arguments:
        step_time -- Time between steps
        step_load -- User increase amount at each step
        spawn_rate -- Users to stop/start per second at every step
        time_limit -- Time limit in seconds
    """
    
    step_time = 60
    step_load = 500
    spawn_rate = 50
    time_limit = 600
    
    def tick(self):
        run_time = self.get_run_time()
        
        if run_time > self.time_limit:
            return None
        
        current_step = run_time // self.step_time
        return (current_step + 1) * self.step_load, self.spawn_rate

# Events for custom logging
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("🚀 Load test starting...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("✅ Load test completed")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time}ms")
    print(f"Requests per second: {environment.stats.total.total_rps}")
