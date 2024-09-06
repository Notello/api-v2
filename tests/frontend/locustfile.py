from locust import HttpUser, task, constant

class WebsiteUser(HttpUser):
    wait_time = constant(1)

    @task
    def landing_page(self):
        self.client.get("/landing-page")

if __name__ == "__main__":
    import os
    os.system("locust -f " + __file__)