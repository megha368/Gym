// The "My bookings" page: passes, booked classes and waitlist.
// Only Bookings is called. Bookings itself asks Scheduling for the class details; if
// Scheduling is down, the bookings are still listed, without their details.
"use strict";

const PASS_LABELS = { drop_in: "Drop-in", class_pack: "Class pack", membership: "Membership" };

startPage();
if (!auth.member()) {
  goToLogin();
} else {
  document.getElementById("buy-pass").addEventListener("submit", buyPass);
  loadAll();
}

function loadAll() {
  loadPasses();
  loadBookings();
}

async function run(action, successMessage) {
  clearMessages();
  try {
    await action();
    showMessage(successMessage, "success");
  } catch (error) {
    if (error.status === 401) return goToLogin();
    showMessage(error.message);
  }
  loadAll();
}

// ---------- passes ----------

async function loadPasses() {
  const container = document.getElementById("passes");
  let passes;
  try {
    passes = (await api("bookings", "/passes")).passes;
  } catch (error) {
    if (error.status === 401) return goToLogin();
    container.replaceChildren(el("p", { class: "flash error" }, error.message));
    return;
  }
  if (passes.length === 0) {
    container.replaceChildren(el("p", { class: "muted" }, "You don't have a pass yet. You need one to book a class."));
    return;
  }
  container.replaceChildren(
    el("table", {},
      el("tr", {}, el("th", {}, "Pass"), el("th", {}, "Classes left"), el("th", {}, "Expires"), el("th", {})),
      passes.map((p) =>
        el("tr", {},
          el("td", {}, PASS_LABELS[p.type] || p.type),
          el("td", {}, p.remaining_uses === null ? "Unlimited" : `${p.remaining_uses} left`),
          el("td", {}, p.expires_at ? fmt.date(p.expires_at) : "Never"),
          el("td", {}, p.is_valid
            ? el("span", { class: "pill open" }, "Active")
            : el("span", { class: "pill" }, "Used up / expired")),
        )),
    ),
  );
}

function buyPass(event) {
  event.preventDefault();
  const passType = new FormData(event.target).get("pass_type");
  run(() => api("bookings", "/passes", { method: "POST", body: { pass_type: passType } }), "Pass added to your account.");
}

// ---------- bookings and waitlist ----------

async function loadBookings() {
  const bookingsBox = document.getElementById("bookings");
  const waitlistBox = document.getElementById("waitlist");
  let data;
  try {
    data = await api("bookings", "/bookings");
  } catch (error) {
    if (error.status === 401) return goToLogin();
    bookingsBox.replaceChildren(el("p", { class: "flash error" }, error.message));
    return;
  }

  const notice = data.details_missing
    ? el("div", { class: "flash error" },
        "Class details are temporarily unavailable, so some classes are shown without their name and time. " +
        "Your bookings are safe. Try again in a minute.")
    : null;

  if (data.bookings.length === 0) {
    bookingsBox.replaceChildren(notice || "",
      el("p", { class: "muted" }, "Nothing booked yet. ", el("a", { href: "index.html" }, "Browse the schedule"), "."));
  } else {
    bookingsBox.replaceChildren(notice || "", el("ul", { class: "sessions" }, data.bookings.map(bookingRow)));
  }

  waitlistBox.replaceChildren(
    ...(data.waitlist.length === 0 ? [] : [
      el("h2", {}, "On the waitlist"),
      el("ul", { class: "sessions" }, data.waitlist.map(waitlistRow)),
    ]),
  );
}

function classInfo(item, fallbackLabel) {
  if (!item.details_available) {
    return [
      el("div", { class: "time wide" }, "Time unavailable"),
      el("div", { class: "info" }, el("strong", {}, fallbackLabel), el("span", { class: "muted" }, "(details unavailable)")),
    ];
  }
  return [
    el("div", { class: "time wide" }, fmt.dateTime(item.start_time)),
    el("div", { class: "info" }, el("strong", {}, item.class_name), el("span", { class: "muted" }, `with ${item.instructor_name}`)),
  ];
}

function bookingRow(b) {
  let action;
  if (!b.details_available) {
    action = el("span", { class: "pill" }, "Cancel unavailable");
  } else if (b.session_status === "cancelled") {
    action = el("span", { class: "pill full" }, "Class cancelled by the studio");
  } else if (b.can_cancel) {
    action = el("button", {
      class: "btn small danger",
      onclick: () => run(
        () => api("bookings", `/bookings/${b.booking_id}/cancel`, { method: "POST" }),
        "Booking cancelled, and any pass credit was returned.",
      ),
    }, "Cancel");
  } else {
    action = el("span", { class: "pill" }, "Past");
  }
  return el("li", { class: "session" }, ...classInfo(b, "Booked class"), el("div", {}, action));
}

function waitlistRow(w) {
  return el("li", { class: "session" },
    ...classInfo(w, "Waitlisted class"),
    el("div", {}, el("span", { class: "pill wait" }, `Position #${w.position}`)),
    el("div", {}, el("button", {
      class: "btn small secondary",
      onclick: () => run(() => api("bookings", `/waitlist/${w.session_id}`, { method: "DELETE" }), "You left the waitlist."),
    }, "Leave")),
  );
}
