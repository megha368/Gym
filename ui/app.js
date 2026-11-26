// Shared by every page: calling the two services, the login token, the header,
// messages, and date formatting. Each page has its own small script on top of this.
"use strict";

const CONFIG = window.APP_CONFIG; // set in config.js

// Generous on purpose: on Azure a service that has scaled to zero may take up to a
// minute to start and wake its database.
const REQUEST_TIMEOUT_MS = 60000;

// ---------- the login token, kept in this browser (localStorage) ----------

const auth = {
  token: () => localStorage.getItem("token"),
  member() {
    try {
      return JSON.parse(localStorage.getItem("member"));
    } catch {
      return null;
    }
  },
  save(data) {
    localStorage.setItem("token", data.token);
    localStorage.setItem("member", JSON.stringify(data.member));
  },
  clear() {
    localStorage.removeItem("token");
    localStorage.removeItem("member");
  },
};

// ---------- calling the services ----------

class ApiError extends Error {
  // status 0 means the service couldn't be reached at all
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// Cold starts on Azure: after a quiet period, the first request starts the container and
// wakes its database. Until it's ready, Azure itself answers 503 ("App port is not ready")
// without passing the request to our code, so it is safe to send it again.
const COLD_START_RETRIES = 6;
const COLD_START_WAIT_MS = 10000;

// Call a service ("scheduling" or "bookings"). Returns the JSON answer, or throws an
// ApiError whose message can be shown to the user.
async function api(service, path, options = {}) {
  for (let attempt = 0; ; attempt++) {
    try {
      const data = await apiOnce(service, path, options);
      hideStartingUp();
      return data;
    } catch (error) {
      if (!error.coldStart || attempt >= COLD_START_RETRIES) {
        hideStartingUp();
        throw error;
      }
      showStartingUp();
      await new Promise((resolve) => setTimeout(resolve, COLD_START_WAIT_MS));
    }
  }
}

function showStartingUp() {
  if (document.getElementById("starting-up")) return;
  document.getElementById("messages").prepend(el("div", { id: "starting-up", class: "flash" },
    "The system is starting up after a quiet period. This can take up to a minute, please wait…"));
}

function hideStartingUp() {
  document.getElementById("starting-up")?.remove();
}

async function apiOnce(service, path, { method = "GET", body } = {}) {
  const base = service === "scheduling" ? CONFIG.SCHEDULING_URL : CONFIG.BOOKINGS_URL;
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (service === "bookings" && auth.token()) headers["Authorization"] = `Bearer ${auth.token()}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetch(base + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(`The ${service} service can't be reached right now. Please try again in a minute.`, 0);
  } finally {
    clearTimeout(timer);
  }

  let data = {};
  try {
    data = await response.json();
  } catch {
    // empty or non-JSON answer
  }
  if (response.status === 401 && service === "bookings") auth.clear(); // token expired or invalid
  if (!response.ok) {
    const error = new ApiError(data.error || `Request failed (${response.status})`, response.status);
    // A 503 without our own {"error": ...} body comes from Azure, not from our code: cold start
    error.coldStart = response.status === 503 && !data.error;
    throw error;
  }
  return data;
}

// For pages that need a logged-in member: send them to the login page.
function goToLogin() {
  flashNext("Please log in first.", "error");
  location.href = "login.html";
}

// ---------- building the page ----------

// Create an element. Text is always added as text, never as HTML, so data from the
// services (like a member's name) can't inject code into the page.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "onclick") node.addEventListener("click", value);
    else if (key === "onsubmit") node.addEventListener("submit", value);
    else if (value !== null && value !== undefined && value !== false) node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  }
  return node;
}

// A message shown after the next page loads (like Flask's flash()).
function flashNext(message, kind = "success") {
  sessionStorage.setItem("flash", JSON.stringify({ message, kind }));
}

function showMessage(message, kind = "error") {
  document.getElementById("messages").append(el("div", { class: `flash ${kind}` }, message));
}

function clearMessages() {
  document.getElementById("messages").replaceChildren();
}

function renderHeader() {
  const member = auth.member();
  const links = [el("a", { href: "index.html" }, "Schedule")];
  if (member) {
    links.push(
      el("a", { href: "bookings.html" }, "My bookings"),
      el("button", {
        class: "link-button",
        onclick: () => {
          auth.clear();
          flashNext("You are logged out.");
          location.href = "index.html";
        },
      }, `Log out (${member.name})`),
    );
  } else {
    links.push(el("a", { href: "login.html" }, "Log in"), el("a", { class: "btn small", href: "register.html" }, "Join"));
  }
  document.getElementById("nav").replaceChildren(...links);
}

// Every page calls this first.
function startPage() {
  renderHeader();
  const pending = sessionStorage.getItem("flash");
  if (pending) {
    sessionStorage.removeItem("flash");
    const { message, kind } = JSON.parse(pending);
    showMessage(message, kind);
  }
}

// ---------- dates (the services send times like "2026-11-18T19:00:00", local time) ----------

const fmt = {
  day: (iso) => new Date(iso).toLocaleDateString("en-GB", { weekday: "long", day: "2-digit", month: "long" }),
  clock: (iso) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
  dateTime: (iso) =>
    `${new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" })}, ${fmt.clock(iso)}`,
  date: (iso) => new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }),
};
