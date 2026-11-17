// Where the two services are. The UI reads these instead of having addresses written
// into its code.
//
// This file is for running locally with docker compose. The deploy pipeline replaces it
// with the services' Azure URLs before uploading the UI to Azure Static Web Apps.
window.APP_CONFIG = {
  SCHEDULING_URL: "http://localhost:8001",
  BOOKINGS_URL: "http://localhost:8000",
};
