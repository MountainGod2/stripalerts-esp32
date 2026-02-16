import QrScanner from "./qr-scanner.min.js";
import { BleClient } from "./ble-client.js";

// Constants
const STEPS = {
  DEVICE: 1,
  WIFI: 2,
  API: 3,
  CONFIRM: 4,
};

// Application State
const ble = new BleClient();
const state = {
  ssid: "",
  password: "",
  apiUrl: "",
  currentStep: STEPS.DEVICE,
  deviceReady: false,
  isConfigEventsComplete: false,
  waitingForSave: false,
  wifiTestSuccess: false,
};

let qrScanner = null;
let qrActive = false;
let wifiTestTimer = null;

// --- UI Helpers ---

const dismissKeyboard = () => {
  const active = document.activeElement;
  if (active?.matches("input, textarea")) {
    active.blur();
  }
};

const showStep = (stepNum) => {
  dismissKeyboard();

  if (state.currentStep === STEPS.API && stepNum !== STEPS.API) {
    stopQrScan(false);
  }

  document
    .querySelectorAll(".step-content")
    .forEach((el) => el.classList.add("hidden"));
  document.getElementById(`step${stepNum}`).classList.remove("hidden");

  document
    .querySelectorAll(".step")
    .forEach((el) => el.classList.remove("active"));
  document
    .querySelector(`.step[data-step="${stepNum}"]`)
    .classList.add("active");

  state.currentStep = stepNum;

  if (stepNum === STEPS.CONFIRM) {
    hideError("confirmError");
    showElement("confirmRebootInfo");
  }
};

const markStepComplete = (stepNum) => {
  document
    .querySelector(`.step[data-step="${stepNum}"]`)
    .classList.add("complete");
};

const showError = (elementId, msg) => {
  const el = document.getElementById(elementId);
  el.textContent = msg;
  el.style.display = "block";
};

const hideError = (elementId) => {
  document.getElementById(elementId).style.display = "none";
};

const showElement = (id) => {
  document.getElementById(id).style.display = "block";
};

const hideElement = (id) => {
  document.getElementById(id).style.display = "none";
};

// --- Validation ---

const isValidApiUrl = (input) => {
  try {
    const url = new URL(String(input ?? "").trim());
    return url.protocol === "https:" && url.pathname.includes("/events/");
  } catch {
    return false;
  }
};

const getApiUrlSummary = (input) => {
  try {
    const url = new URL(String(input ?? "").trim());
    const parts = url.pathname.split("/").filter(Boolean);
    const eventIndex = parts.indexOf("events");
    const username = eventIndex >= 0 ? parts[eventIndex + 1] : "";
    return { username, isTestbed: url.hostname.includes("testbed") };
  } catch {
    return { username: "", isTestbed: false };
  }
};

// --- BLE Handling ---

const handleDisconnect = async () => {
  console.log("Device disconnected");
  if (state.isConfigEventsComplete) return;

  state.deviceReady = false;

  // Auto-reconnect if within setup flow
  if (state.currentStep >= 1 && state.currentStep <= 4) {
    try {
      console.log("Attempting to reconnect...");
      await ble.connect();
      console.log("Reconnected");
    } catch (e) {
      console.error("Reconnect failed", e);
      showError("stepError", "Device disconnected. Tap Scan to reconnect.");
      showElement("deviceContainer");
    }
  }
};

const onStatusUpdate = (status) => {
  console.log("Status:", status);

  // Update subtitle if on step 1
  if (state.currentStep === STEPS.DEVICE) {
    const sub = document.getElementById("scanSubtitle");
    sub.textContent = `Status: ${status}`;
    sub.style.display = "block";
  }

  if (status === "Ready") {
    state.deviceReady = true;
  }

  if (status.startsWith("WiFi failed") && state.currentStep === STEPS.WIFI) {
    showError("wifiError", status);
    document.getElementById("wifiNextBtn").disabled = false;
    document.getElementById("wifiNextBtn").textContent = "Continue";
  }

  if (
    state.currentStep === STEPS.CONFIRM &&
    (status.startsWith("Saving") || status.startsWith("Saved"))
  ) {
    document.getElementById("confirmInfo").textContent = status;

    if (status === "Saved" && state.waitingForSave) {
      state.waitingForSave = false;
      state.isConfigEventsComplete = true;

      hideElement("confirmInfo");
      hideElement("confirmRebootInfo");
      showElement("confirmSuccess");
      document
        .getElementById("confirmSuccess")
        .classList.add("success-animation");
      markStepComplete(STEPS.CONFIRM);

      setTimeout(() => {
        hideElement("confirmBtn");
        hideElement("confirmBackBtn");
      }, 500); // Small delay to let animation start
    }
  }

  if (status.startsWith("Save failed") && state.currentStep === STEPS.CONFIRM) {
    state.waitingForSave = false;
    const btn = document.getElementById("confirmBtn");
    btn.disabled = false;
    showError("confirmError", status);
  }
};

const onNetworksUpdate = (networks) => {
  if (!Array.isArray(networks)) return;

  const list = document.getElementById("networksList");
  list.innerHTML = "";

  if (networks.length === 0) {
    list.innerHTML = '<div class="network-empty">No networks found</div>';
    return;
  }

  networks.sort((a, b) => b.rssi - a.rssi);
  networks.slice(0, 5).forEach((net) => {
    const el = document.createElement("div");
    el.className = "network-item";
    const strength =
      net.rssi > -60 ? "Strong" : net.rssi > -75 ? "Good" : "Weak";

    const ssidSpan = document.createElement("span");
    ssidSpan.textContent = net.ssid || "Unknown";
    el.appendChild(ssidSpan);

    const strengthSpan = document.createElement("span");
    strengthSpan.className = "network-strength";
    strengthSpan.textContent = strength;
    el.appendChild(strengthSpan);

    el.onclick = () => {
      document.getElementById("wifiSsid").value = net.ssid;
      document.getElementById("wifiPassword").focus();
    };
    list.appendChild(el);
  });
};

const onWifiTestUpdate = (result) => {
  console.log("WiFi Test Result:", result);
  // Clear timeout to avoid stale "Test timed out" if we moved on
  if (wifiTestTimer) {
    clearTimeout(wifiTestTimer);
    wifiTestTimer = null;
  }

  if (state.currentStep !== STEPS.WIFI) return;

  const btn = document.getElementById("wifiNextBtn");

  if (result === "success") {
    state.wifiTestSuccess = true;
    btn.disabled = false;
    btn.textContent = "Continue";
    markStepComplete(STEPS.WIFI);
    showStep(STEPS.API);
  } else if (result === "failed") {
    state.wifiTestSuccess = false;
    btn.disabled = false;
    btn.textContent = "Continue";
    showError("wifiError", "Connection failed. Check password.");
  }
};

// Bind BLE events
ble.on("disconnected", handleDisconnect);
ble.on("status", onStatusUpdate);
ble.on("networks", onNetworksUpdate);
ble.on("wifiTest", onWifiTestUpdate);

// --- Step Actions ---

const startScan = async () => {
  hideError("stepError");
  showElement("scanLoading");
  hideElement("deviceContainer");

  try {
    await ble.scan();
    hideElement("scanLoading");
    await ble.connect();

    markStepComplete(STEPS.DEVICE);

    showStep(STEPS.WIFI);

    // Request initial network scan after connection is fully established
    try {
      await new Promise((r) => setTimeout(r, 500));
      await ble.write("wifiTest", "rescan");
    } catch (e) {
      console.error("Initial network scan failed:", e);
    }
  } catch (e) {
    hideElement("scanLoading");
    showElement("deviceContainer");
    showError("stepError", e.message);
  }
};

const wifiNext = async () => {
  const ssid = document.getElementById("wifiSsid").value.trim();
  const password = document.getElementById("wifiPassword").value;

  if (!ssid) return showError("wifiError", "Enter network name");
  if (!password) return showError("wifiError", "Enter password");

  state.ssid = ssid;
  state.password = password;

  dismissKeyboard();
  hideError("wifiError");

  const btn = document.getElementById("wifiNextBtn");
  btn.disabled = true;
  btn.textContent = "Testing WiFi...";
  state.wifiTestSuccess = false;

  try {
    await ble.write("ssid", ssid);
    await new Promise((r) => setTimeout(r, 100));
    await ble.write("password", password);
    // Wait for backend debounce to complete before testing
    await new Promise((r) => setTimeout(r, 600));
    await ble.write("wifiTest", "test");

    // Response handled by onWifiTestUpdate or timeout
    wifiTestTimer = setTimeout(() => {
      wifiTestTimer = null;
      if (btn.disabled) {
        btn.disabled = false;
        btn.textContent = "Continue";
        // Don't show error if we moved on
        if (state.currentStep === STEPS.WIFI) {
          showError("wifiError", "Test timed out");
        }
      }
    }, 15000);
  } catch (e) {
    if (wifiTestTimer) {
      clearTimeout(wifiTestTimer);
      wifiTestTimer = null;
    }
    btn.disabled = false;
    btn.textContent = "Continue";
    showError("wifiError", e.message);
  }
};

const apiNext = () => {
  const url = document.getElementById("apiUrl").value.trim();
  if (!isValidApiUrl(url)) {
    return showError("apiError", "Invalid API URL");
  }

  state.apiUrl = url;
  hideError("apiError");
  markStepComplete(STEPS.API);

  // Summary
  const { username, isTestbed } = getApiUrlSummary(url);
  document.getElementById("confirmSsid").textContent = state.ssid;
  document.getElementById("confirmUsername").textContent = username || "?";
  document.getElementById("confirmTestbed").textContent = isTestbed
    ? "Yes"
    : "No";

  showStep(STEPS.CONFIRM);
};

const sendConfig = async () => {
  const btn = document.getElementById("confirmBtn");
  btn.disabled = true;

  hideError("confirmError");

  if (!state.wifiTestSuccess) {
    btn.disabled = false;
    return showError("confirmError", "WiFi test has not succeeded.");
  }

  if (!isValidApiUrl(state.apiUrl)) {
    btn.disabled = false;
    return showError("confirmError", "API URL is invalid.");
  }

  try {
    await ble.write("ssid", state.ssid);
    await new Promise((r) => setTimeout(r, 100));
    await ble.write("password", state.password);
    await new Promise((r) => setTimeout(r, 100));
    await ble.write("apiUrl", state.apiUrl);
    await new Promise((r) => setTimeout(r, 100));

    // Send save command
    state.waitingForSave = true;
    showElement("confirmInfo"); // Ensure it's visible or keep currently visible
    document.getElementById("confirmInfo").textContent = "Saving...";

    await ble.write("wifiTest", "save");

    // Timeout fallback if "Saved" event doesn't arrive
    setTimeout(() => {
      if (state.waitingForSave) {
        state.waitingForSave = false;
        btn.disabled = false;
        hideElement("confirmRebootInfo");
        showError("confirmError", "Save timed out. Please try again.");
      }
    }, 10000);
  } catch (e) {
    state.waitingForSave = false;
    btn.disabled = false;
    hideElement("confirmRebootInfo");
    showError("confirmError", e.message);
  }
};

// --- QR Code ---

const handleQrResult = (result) => {
  const data = result?.data || result;
  if (isValidApiUrl(data)) {
    document.getElementById("apiUrl").value = data;
    state.apiUrl = data;
    document.getElementById("apiInfo").style.display = "block";
    stopQrScan(true);
  }
};

const startQrScan = async () => {
  const video = document.getElementById("qrPreview");
  hideError("apiError");

  if (!qrScanner) {
    qrScanner = new QrScanner(video, handleQrResult, {
      preferredCamera: "environment",
      returnDetailedScanResult: true,
    });
  }

  try {
    await qrScanner.start();
    qrActive = true;
    document.getElementById("qrContainer").classList.remove("hidden");
    toggleQrButtons(true);
  } catch (e) {
    showError("apiError", "Camera error: " + e.message);
  }
};

const stopQrScan = (destroy = false) => {
  if (qrScanner) {
    qrScanner.stop();
    qrActive = false;
    if (destroy) {
      qrScanner.destroy();
      qrScanner = null;
    }
  }
  document.getElementById("qrContainer").classList.add("hidden");
  toggleQrButtons(false);
};

const toggleQrButtons = (scanning) => {
  document.getElementById("scanQrBtn").style.display = scanning
    ? "none"
    : "block";
  document.getElementById("stopQrBtn").style.display = scanning
    ? "block"
    : "none";
};

// --- Event Wiring ---

document.getElementById("manualScanBtn").addEventListener("click", startScan);

document.getElementById("wifiNextBtn").addEventListener("click", wifiNext);
document
  .getElementById("wifiBackBtn")
  .addEventListener("click", () => showStep(STEPS.DEVICE));

document.getElementById("scanQrBtn").addEventListener("click", startQrScan);
document
  .getElementById("stopQrBtn")
  .addEventListener("click", () => stopQrScan(false));

document.getElementById("apiNextBtn").addEventListener("click", apiNext);
document
  .getElementById("apiBackBtn")
  .addEventListener("click", () => showStep(STEPS.WIFI));

document.getElementById("confirmBtn").addEventListener("click", sendConfig);
document
  .getElementById("confirmBackBtn")
  .addEventListener("click", () => showStep(STEPS.API));

document.getElementById("rescanBtn").addEventListener("click", async () => {
  try {
    await ble.write("wifiTest", "rescan");
  } catch (e) {
    console.error(e);
  }
});

// Window events
window.addEventListener("pagehide", () => stopQrScan(true));
window.addEventListener("load", () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
});
