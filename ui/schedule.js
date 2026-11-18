// The schedule page. It calls BOTH services and combines their answers:
//   Scheduling: which classes are coming up (name, instructor, time, capacity)
//   Bookings:   how many spots are taken, and whether I'm booked or waitlisted
// If Bookings is down, the classes are still shown, just without spots and booking.
"use strict";

startPage();
loadSchedule();

async function loadSchedule() {
  const container = document.getElementById("schedule");

  let sessions;
  try {
    sessions = await api("scheduling", "/sessions");
  } catch {
    container.replaceChildren(
      el("div", { class: "flash error" }, "The class schedule is temporarily unavailable. Please try again in a minute."),
    );
    return;
  }
  if (sessions.length === 0) {
    container.replaceChildren(el("p", { class: "muted" }, "No upcoming classes yet."));
    return;
  }

  let availability = null; // stays null if Bookings can't answer
  try {
    const ids = sessions.map((s) => s.id).join(",");
    availability = (await api("bookings", `/availability?session_ids=${ids}`)).sessions;
  } catch {
    showMessage("Booking is temporarily unavailable, so spots left aren't shown. You can still browse the classes.");
  }

  // Group the sessions by day (the first 10 characters of start_time are the date)
  const days = new Map();
  for (const session of sessions) {
    const day = session.start_time.slice(0, 10);
    if (!days.has(day)) days.set(day, []);
    days.get(day).push(session);
  }

  const parts = [];
  for (const [day, daySessions] of days) {
    parts.push(el("h2", { class: "day" }, fmt.day(day)));
    parts.push(el("ul", { class: "sessions" }, daySessions.map((s) => sessionRow(s, availability?.[s.id]))));
  }
  container.replaceChildren(...parts);
}

function sessionRow(session, mine) {
  let spots = null;
  let action = null;

  if (mine) {
    const spotsLeft = Math.max(session.capacity - mine.booked, 0);
    spots = spotsLeft === 0
      ? el("span", { class: "pill full" }, "Full")
      : el("span", { class: "pill open" }, `${spotsLeft} of ${session.capacity} spots left`);

    if (mine.member_status === "booked") {
      action = el("span", { class: "pill booked" }, "Booked ✓");
    } else if (mine.member_status === "waitlisted") {
      action = el("span", { class: "pill wait" }, `Waitlist #${mine.waitlist_position}`);
    } else if (auth.member()) {
      action = el("button", { class: "btn small", onclick: () => book(session.id) }, spotsLeft === 0 ? "Join waitlist" : "Book");
    } else {
      action = el("a", { class: "btn small secondary", href: "login.html" }, "Log in to book");
    }
  }

  return el("li", { class: "session" },
    el("div", { class: "time" }, fmt.clock(session.start_time)),
    el("div", { class: "info" },
      el("strong", {}, session.class_name),
      el("span", { class: "muted" }, `with ${session.instructor_name}`),
    ),
    el("div", {}, spots),
    el("div", {}, action),
  );
}

async function book(sessionId) {
  clearMessages();
  try {
    const result = await api("bookings", "/bookings", { method: "POST", body: { session_id: sessionId } });
    if (result.status === "confirmed") showMessage("Booked! See you there.", "success");
    else showMessage(`The class is full, so you are #${result.position} on the waitlist.`, "success");
  } catch (error) {
    if (error.status === 401) return goToLogin();
    showMessage(error.message);
  }
  loadSchedule();
}
