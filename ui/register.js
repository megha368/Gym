"use strict";

startPage();
document.getElementById("register").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessages();
  const form = new FormData(event.target);
  try {
    const result = await api("bookings", "/auth/register", {
      method: "POST",
      body: { name: form.get("name"), email: form.get("email"), password: form.get("password") },
    });
    auth.save(result);
    flashNext("Welcome! Your account is ready.");
    location.href = "index.html";
  } catch (error) {
    showMessage(error.message);
  }
});
