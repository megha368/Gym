"use strict";

startPage();
document.getElementById("login").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessages();
  const form = new FormData(event.target);
  try {
    const result = await api("bookings", "/auth/login", {
      method: "POST",
      body: { email: form.get("email"), password: form.get("password") },
    });
    auth.save(result);
    location.href = "index.html";
  } catch (error) {
    showMessage(error.message);
  }
});
