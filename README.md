# Modbus Integration & Visualization Suite

This project aims to build a modular, extensible suite of tools to simulate Modbus devices, integrate their data into modern data pipelines, and visualize it through a web-based dashboard.

## Core Goals

*   **Modbus Simulation:** Provide a configurable Modbus TCP simulator capable of mimicking various device behaviors and data types, including dynamic data trends.
*   **Data Integration:** Enable seamless collection of Modbus data and its integration with:
    *   **InfluxDB:** For time-series data storage and historical analysis.
    *   **MQTT:** For real-time data dissemination and receiving control commands.
*   **Web API & Dashboard:** Offer a backend API and a user-friendly web dashboard for:
    *   Real-time data monitoring.
    *   Historical data querying and visualization.
    *   Sending control commands to Modbus devices.
    *   User authentication and secure access.
*   **Containerization:** Ensure all components (simulator, gateway, API, dashboard, databases, brokers) are containerized using Docker for easy setup, deployment, and scalability.

## Project Roadmap

### Milestone 1: Project Setup & Modbus Simulator (Completed)
*   **Project Initialization:** Established root directory, base file structure.
*   **Modbus Simulator (`simulator/`):**
    *   Developed a Python-based Modbus TCP slave server using `pymodbus`.
    *   Implemented YAML-based configuration for device maps and register definitions.
    *   Added data simulation capabilities (linear, random, sinusoidal trends).
    *   Containerized the simulator service.
*   **Basic Docker Compose:** Initial `docker-compose.yml` with the simulator service.

### Milestone 2: Gateway + InfluxDB/MQTT Bridge (Completed)
*   **Gateway Service (`gateway/`):**
    *   Developed a Python service to poll data from the Modbus simulator.
    *   Configuration via `gateway/config.yaml` for Modbus targets, polling intervals, InfluxDB, and MQTT settings.
    *   Pushes polled data to InfluxDB.
    *   Publishes polled data to MQTT topics.
    *   Subscribes to an MQTT topic for control commands (e.g., write to register/coil).
*   **MQTT Broker:** Added Mosquitto MQTT broker service to `docker-compose.yml`.
*   **InfluxDB:** Added InfluxDB service to `docker-compose.yml`.
*   **Containerization:** Dockerized the gateway service.
*   **Docker Compose Updates:** Linked services in `docker-compose.yml`.

### Milestone 3: API & Web Dashboard (Partially Completed)
*   **A. API Layer (`api/`) (Completed)**
    *   **Framework:** FastAPI with Python.
    *   **Endpoints:**
        *   `/api/v1/auth/token`: JWT-based authentication.
        *   `/api/v1/data/historical` (POST): Query historical data from InfluxDB (protected).
        *   `/api/v1/control/write_register` (POST): Publish Modbus write commands to MQTT (protected).
        *   `/ws/realtime`: WebSocket endpoint for streaming real-time data.
    *   **Services:** `InfluxDBService` for data querying, `MQTTService` for handling real-time data flow to WebSockets and publishing control commands.
    *   **Configuration:** `api/config.yaml` for InfluxDB, MQTT, and JWT settings.
    *   **Containerization:** Dockerized the API service.
*   **B. Web Dashboard (`dashboard/`) (Client-side Logic Implemented)**
    *   **Framework:** React with TypeScript, Vite for bundling.
    *   **Styling:** Tailwind CSS.
    *   **Routing:** `react-router-dom` for navigation (`/`, `/login`, `/dashboard`).
    *   **Core Features Implemented:**
        *   Login page (`LoginPage.tsx`): Authenticates against the API, stores JWT.
        *   Dashboard page (`DashboardPage.tsx`):
            *   Protected: Redirects to login if not authenticated.
            *   Fetches and displays historical data from the API.
            *   Connects to WebSocket for real-time data updates.
            *   Logout functionality.
        *   API service utility (`apiService.ts`) for frontend API calls.
        *   Shared data models (`models.ts`).
    *   **Containerization:** Multi-stage Dockerfile serving static build with Nginx.
*   **Docker Compose Updates:** Added API and Dashboard services, configured ports and dependencies.

### Milestone 4: Advanced Features & Refinements (Next Steps / Future)
*   **Dashboard Enhancements:**
    *   UI for Modbus write commands (interacting with `api/routes/control_routes.py`).
    *   Data visualization (e.g., charts for historical and real-time data).
    *   User interface for selecting historical data query parameters.
    *   Improved error handling and user feedback.
    *   Robust WebSocket reconnection logic.
    *   More sophisticated state management (e.g., Context API, Zustand, or Redux).
*   **Grafana Integration (`grafana/`):** Configure Grafana for advanced visualization and dashboards, connecting to InfluxDB.
*   **Data Analytics (`analytics/`):** Placeholder for potential future data processing or machine learning modules.
*   **Testing:** Implement unit and integration tests for all services.
*   **Documentation:**
    *   Detailed setup and usage instructions for each component.
    *   API documentation (e.g., Swagger UI via FastAPI).
    *   Deployment guides.
*   **Configuration & Security:**
    *   Centralized and more secure configuration management (e.g., using environment variables consistently, Vault).
    *   Review and enhance security aspects across all services.

## Setup Instructions

(To be detailed further - for now, ensure Docker and Docker Compose are installed)

1.  Clone the repository.
2.  Navigate to the project root.
3.  Run `docker-compose up --build -d` to build and start all services in detached mode.
    *   Simulator accessible on port `5020`.
    *   Gateway connects to Simulator, InfluxDB, and MQTT.
    *   API accessible on port `8000`.
    *   Dashboard accessible on port `3000`.
    *   MQTT broker on port `1883` (TCP) and `9001` (WebSockets).
    *   InfluxDB on port `8086`.
    *   Grafana on port `3001`.

(Default credentials and setup for InfluxDB/Grafana will need to be documented or automated)
