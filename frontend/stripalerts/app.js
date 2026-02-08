import QrScanner from "./qr-scanner.min.js";

// Constants
const CHUNK_SIZE = 18;
const MAX_RETRIES = 30;
const RETRY_DELAY_MS = 1000;
const CHUNK_DELAY_MS = 50;
const WRITE_DELAY_MS = 500;

const SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
const CHAR_UUIDS = {
  ssid: "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
  password: "6e400003-b5a3-f393-e0a9-e50e24dcca9e",
  apiUrl: "6e400004-b5a3-f393-e0a9-e50e24dcca9e",
  status: "6e400005-b5a3-f393-e0a9-e50e24dcca9e",
  networks: "6e400006-b5a3-f393-e0a9-e50e24dcca9e",
  wifiTest: "6e400007-b5a3-f393-e0a9-e50e24dcca9e",
};

const STEPS = {
  DEVICE: 1,
  WIFI: 2,
  API: 3,
  CONFIRM: 4,
};

// Text encoding/decoding
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

// Validation
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

// UTF-8 chunking
const splitIntoUtf8Chunks = (text, maxBytes) => {
  const allBytes = textEncoder.encode(text ?? "");
  if (allBytes.length === 0) return [];

  const chunks = [];
  let offset = 0;

  while (offset < allBytes.length) {
    let end = Math.min(offset + maxBytes, allBytes.length);

    // Avoid splitting multi-byte UTF-8 sequences
    // If byte at 'end' is a continuation byte (10xxxxxx), backtrack
    while (end > offset && (allBytes[end] & 0xc0) === 0x80) {
      end--;
    }

    chunks.push(allBytes.subarray(offset, end));
    offset = end;
  }
  return chunks;
};

const decodeGattValue = (value) => {
  if (!value) return "";

  if (value instanceof DataView) {
    const view = new Uint8Array(
      value.buffer,
      value.byteOffset,
      value.byteLength,
    );
    return textDecoder.decode(view);
  }

  if (value instanceof ArrayBuffer) {
    return textDecoder.decode(new Uint8Array(value));
  }

  return textDecoder.decode(value);
};

// Application state
const state = {
  device: null,
  server: null,
  characteristics: {},
  notifications: { status: false, networks: false, wifiTest: false },
  ssid: "",
  password: "",
  apiUrl: "",
  currentStep: STEPS.DEVICE,
  deviceReady: false,
  isConfigEventsComplete: false,
};

// QR Scanner state
let qrScanner = null;
let qrActive = false;

// UI Helpers
const dismissKeyboard = () => {
  const active = document.activeElement;
  if (!active?.matches("input, textarea")) {
    active?.blur();
    return;
  }

  active.blur();
  try {
    const originalReadonly = active.readOnly;
    active.readOnly = true;
    setTimeout(() => {
      active.readOnly = originalReadonly;
      active.blur();
    }, 50);
  } catch {}
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

const showElement = (id) => {
  document.getElementById(id).style.display = "block";
};

const hideElement = (id) => {
  document.getElementById(id).style.display = "none";
};

const toggleQrButtons = (scanning) => {
  document.getElementById("scanQrBtn").style.display = scanning
    ? "none"
    : "block";
  document.getElementById("stopQrBtn").style.display = scanning
    ? "block"
    : "none";
};

const showConfigSuccess = () => {
  state.isConfigEventsComplete = true; 
  hideElement("confirmInfo");
  showElement("confirmSuccess");
  document.getElementById("confirmSuccess").classList.add("success-animation");
  markStepComplete(STEPS.CONFIRM);
  setTimeout(() => {
    hideElement("confirmBtn");
    hideElement("confirmBackBtn");
  }, 2000);
};

const isGattDisconnect = (err) => {
  if (!err) return false;
  const name = String(err.name ?? "");
  const msg = String(err.message ?? "").toLowerCase();
  return (
    name === "NetworkError" ||
    msg.includes("gatt") ||
    msg.includes("disconnect") ||
    msg.includes("not connected") ||
    msg.includes("failed to execute") ||
    msg.includes("device is no longer in range")
  );
};

// Bluetooth GATT Setup
const setupGatt = async () => {
  if (state.device.gatt.connected && state.server) return;

  console.log("Setting up GATT...");
  state.server = await state.device.gatt.connect();
  const service = await state.server.getPrimaryService(SERVICE_UUID);

  // Get all characteristics
  for (const [key, uuid] of Object.entries(CHAR_UUIDS)) {
    state.characteristics[key] = await service.getCharacteristic(uuid);
  }

  state.notifications = { status: false, networks: false, wifiTest: false };

  // Enable notifications
  await enableNotification("status", onStatusNotify);
  await enableNotification("networks", onNetworksNotify);
  await enableNotification("wifiTest", onWifiTestNotify);
};

const enableNotification = async (key, handler) => {
  if (!state.characteristics[key] || state.notifications[key]) return;

  try {
    await state.characteristics[key].startNotifications();
    state.characteristics[key].addEventListener(
      "characteristicvaluechanged",
      handler,
    );
    state.notifications[key] = true;
    console.log(`${key} notifications enabled`);
  } catch (err) {
    console.log(`Error enabling ${key} notifications:`, err);
  }
};

const reconnectToDevice = async () => {
  if (!state.device) throw new Error("No device selected.");
  await setupGatt();
};

// Bluetooth Write Operations
const safeWrite = async (characteristic, text) => {
  const chunks = splitIntoUtf8Chunks(text, CHUNK_SIZE);
  if (chunks.length === 0) {
    // Empty string case: send header only [0x01] to clear buffer
    const payload = new Uint8Array(1);
    payload[0] = 0x01;
    await writeRaw(characteristic, payload);
    return;
  }

  // First chunk with overwrite marker (0x01)
  const firstPayload = new Uint8Array(chunks[0].length + 1);
  firstPayload[0] = 0x01;
  firstPayload.set(chunks[0], 1);
  await writeRaw(characteristic, firstPayload);

  // Remaining chunks with append marker (0x02)
  for (let i = 1; i < chunks.length; i++) {
    await new Promise((r) => setTimeout(r, CHUNK_DELAY_MS));
    const payload = new Uint8Array(chunks[i].length + 1);
    payload[0] = 0x02;
    payload.set(chunks[i], 1);
    await writeRaw(characteristic, payload);
  }
};

const writeRaw = async (characteristic, payload) => {
  try {
    await characteristic.writeValue(payload);
  } catch (err) {
    if (isGattDisconnect(err)) {
      console.log(
        "Write failed due to disconnect; reconnecting and retrying...",
      );
      await reconnectToDevice();
      await characteristic.writeValue(payload);
      return;
    }
    throw err;
  }
};

const safeReadString = async (characteristic) => {
  try {
    const value = await characteristic.readValue();
    return decodeGattValue(value);
  } catch (err) {
    if (isGattDisconnect(err)) {
      console.log(
        "Read failed due to disconnect; reconnecting and retrying...",
      );
      await reconnectToDevice();
      const value = await characteristic.readValue();
      return decodeGattValue(value);
    }
    throw err;
  }
};

const handleWifiFailure = (
  fallbackMsg = "WiFi connection failed. Check your password and try again.",
) => {
  const wifiNextBtn = document.getElementById("wifiNextBtn");
  wifiNextBtn.disabled = false;
  wifiNextBtn.textContent = "Continue";

  const statusChar = state.characteristics.status;
  if (!statusChar) {
    showError("wifiError", fallbackMsg);
    return;
  }

  safeReadString(statusChar)
    .then((statusDetail) => {
      showError("wifiError", statusDetail || fallbackMsg);
    })
    .catch((err) => {
      console.log("Status read failed:", err);
      showError("wifiError", fallbackMsg);
    });
};

const updateStatusDisplay = (status) => {
  if (!status) return;

  if (state.currentStep === STEPS.DEVICE) {
    const subtitle = document.getElementById("scanSubtitle");
    subtitle.textContent = `Device status: ${status}`;
    subtitle.style.display = "block";
  }

  if (
    state.currentStep === STEPS.CONFIRM &&
    (status.startsWith("Saving") ||
      status.startsWith("Saved") ||
      status.startsWith("WiFi"))
  ) {
    const info = document.getElementById("confirmInfo");
    info.textContent = status;
    info.style.display = "block";
  }
};

const onStatusNotify = (event) => {
  const status = decodeGattValue(event.target.value);
  console.log("Status notify:", status);
  state.deviceReady = status === "Ready";
  updateStatusDisplay(status);

  if (status?.startsWith("WiFi failed") && state.currentStep === 2) {
    showError("wifiError", status);
    const wifiNextBtn = document.getElementById("wifiNextBtn");
    wifiNextBtn.disabled = false;
    wifiNextBtn.textContent = "Continue";
  }
};

const onNetworksNotify = (event) => {
  const networksJson = decodeGattValue(event.target.value);
  if (!networksJson) return;

  try {
    const networks = JSON.parse(networksJson);
    if (Array.isArray(networks)) renderNetworkList(networks);
  } catch (err) {
    console.log("Failed to parse networks notify:", err);
  }
};

const onWifiTestNotify = (event) => {
  const testResult = decodeGattValue(event.target.value);
  console.log("WiFi test notify:", testResult);
  if (state.currentStep !== 2) {
    return;
  }

  const wifiNextBtn = document.getElementById("wifiNextBtn");

  if (testResult === "success") {
    wifiNextBtn.disabled = false;
    wifiNextBtn.textContent = "Continue";
    markStepComplete(STEPS.WIFI);
    showStep(STEPS.API);
    return;
  }

  if (testResult === "failed") {
    handleWifiFailure();
    return;
  }
};

const startDeviceScan = async () => {
  showElement("scanLoading");
  hideElement("stepError");
  hideElement("deviceContainer");

  if (!navigator.bluetooth) {
    hideElement("scanLoading");
    showError(
      "stepError",
      "This application requires access to Bluetooth. Please use a native mobile browser (Chrome on Android or Safari on iOS) to proceed.",
    );
    showElement("deviceContainer");
    hideElement("scanSubtitle");
    return;
  }

  try {
    state.device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: "StripAlerts-" }],
      optionalServices: [SERVICE_UUID],
    });
    state.device.addEventListener("gattserverdisconnected", async () => {
      console.log("GATT disconnected event fired");

      if (state.isConfigEventsComplete) {
        console.log("Configuration complete; ignoring disconnect.");
        return;
      }

      state.notifications = { status: false, networks: false, wifiTest: false };
      state.deviceReady = false;

      if (state.currentStep >= 1 && state.currentStep <= 4) {
        try {
          await reconnectToDevice();
          console.log("Auto-reconnect succeeded");
          if (state.currentStep === 2) {
            await loadNetworks();
          }
        } catch (e) {
          console.log("Auto-reconnect failed:", e);
          showError(
            "stepError",
            "Device disconnected. Tap “Scan Again” to reconnect.",
          );
          showElement("deviceContainer");
        }
      }
    });

    hideElement("scanLoading");
    await connectToDevice();
  } catch (err) {
    hideElement("scanLoading");
    if (err.name !== "NotFoundError") {
      showError("stepError", `Bluetooth error: ${err.message}`);
    } else {
      showError(
        "stepError",
        "Device not found. Make sure it is powered on and nearby.",
      );
    }
    showElement("deviceContainer");
  }
  hideElement("scanSubtitle");
  showElement("deviceContainer");
};

const connectToDevice = async () => {
  try {
    await setupGatt();

    state.deviceReady = false;
    markStepComplete(STEPS.DEVICE);
    const ready = await waitForDeviceReady();
    if (!ready) {
      showError(
        "stepError",
        "Device did not become ready. Tap “Scan Again” to retry.",
      );
      showElement("deviceContainer");
      return
    }
    await loadNetworks();

    showStep(STEPS.WIFI);
  } catch (err) {
    showError("stepError", `Connection failed: ${err.message}`);
    showElement("deviceContainer");
  }
};

const waitForDeviceReady = async () => {
  let attempts = 0;

  while (attempts < MAX_RETRIES) {
    if (state.deviceReady) {
      console.log("Device reported ready via notification");
      return true;
    }

    try {
      const status = await safeReadString(state.characteristics.status);
      console.log(`Device status: ${status}`);

      if (status) {
        updateStatusDisplay(status);
      }

      if (status === "Ready") {
        state.deviceReady = true;
        console.log("Device is ready");
        return true;
      }
    } catch (err) {
      console.log("Error reading status:", err);
    }

    await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
    attempts++;
  }

  console.log("Timeout waiting for device to be ready");
  return false;
};

const loadNetworks = async () => {
  try {
    const value = await state.characteristics.networks.readValue();
    let networksJson = decodeGattValue(value);

    if (!networksJson || networksJson === "[]") {
      document.getElementById("networksList").innerHTML =
        '<div class="network-empty">No networks found</div>';
      return;
    }

    const networks = JSON.parse(networksJson);

    if (!Array.isArray(networks)) {
      console.error("Networks is not an array:", typeof networks);
      return;
    }

    renderNetworkList(networks);
  } catch (err) {
    console.error("Error loading networks:", err);
    document.getElementById("networksList").innerHTML =
      '<div class="network-error">Error loading networks</div>';
  }
};

const renderNetworkList = (networks) => {
  const list = document.getElementById("networksList");
  const ssidInput = document.getElementById("wifiSsid");

  list.innerHTML = "";

  if (!networks || networks.length === 0) {
    list.innerHTML = '<div class="network-empty">No networks found</div>';
    return;
  }

  networks.sort((a, b) => b.rssi - a.rssi);
  networks.slice(0, 5).forEach((net) => {
    const option = document.createElement("div");
    option.className = "network-item";

    const strength =
      net.rssi > -60 ? "Strong" : net.rssi > -75 ? "Good" : "Weak";
    option.innerHTML = `<span>${net.ssid || "Unknown"}</span><span class="network-strength">${strength}</span>`;

    option.onclick = () => {
      ssidInput.value = net.ssid;
      document.getElementById("wifiPassword").focus();
    };

    list.appendChild(option);
  });
};

const wifiNext = () => {
  const ssid = document.getElementById("wifiSsid").value.trim();
  const password = document.getElementById("wifiPassword").value;

  if (!ssid) {
    showError("wifiError", "Please enter network name");
    return;
  }

  if (!password) {
    showError("wifiError", "Please enter password");
    return;
  }

  state.ssid = ssid;
  state.password = password;

  dismissKeyboard();

  document.getElementById("wifiError").style.display = "none";
  testWiFi();
};

const testWiFi = async () => {
  const wifiNextBtn = document.getElementById("wifiNextBtn");
  wifiNextBtn.disabled = true;
  wifiNextBtn.textContent = "Testing WiFi...";

  try {
    console.log("Sending WiFi credentials to device...");

    await safeWrite(state.characteristics.ssid, state.ssid);
    await new Promise((r) => setTimeout(r, WRITE_DELAY_MS));

    await safeWrite(state.characteristics.password, state.password);
    await new Promise((r) => setTimeout(r, WRITE_DELAY_MS));

    console.log("Sending test command...");
    await safeWrite(state.characteristics.wifiTest, "test");
    let attempts = 0;
    while (attempts < 30) {
      const testResult = await safeReadString(state.characteristics.wifiTest);
      console.log("WiFi test (fallback read) result:", testResult);

      if (testResult === "success") {
        wifiNextBtn.disabled = false;
        wifiNextBtn.textContent = "Continue";
        markStepComplete(STEPS.WIFI);
        showStep(STEPS.API);
        return;
      }

      if (testResult === "failed") {
        handleWifiFailure();
        return;
      }

      await new Promise((r) => setTimeout(r, WRITE_DELAY_MS));
      attempts++;
    }

    showError("wifiError", "WiFi test timeout. Please try again.");
    wifiNextBtn.disabled = false;
    wifiNextBtn.textContent = "Continue";
  } catch (err) {
    console.error("Error testing WiFi:", err);
    showError("wifiError", `Error testing WiFi: ${err.message}`);
    wifiNextBtn.disabled = false;
    wifiNextBtn.textContent = "Continue";
  }
};

const handleQrResult = (result) => {
  const qrData = result && typeof result === "object" ? result.data : result;
  if (!qrData) return;

  console.log("QR code detected:", qrData);

  if (isValidApiUrl(qrData)) {
    document.getElementById("apiUrl").value = qrData;
    state.apiUrl = qrData;

    document.getElementById("apiInfo").style.display = "block";
    stopQrScan(true);
  }
};

const startQrScan = async () => {
  const video = document.getElementById("qrPreview");
  document.getElementById("apiError").style.display = "none";

  if (!qrScanner) {
    qrScanner = new QrScanner(video, handleQrResult, {
      preferredCamera: "environment",
      returnDetailedScanResult: true,
      onDecodeError: () => {},
    });
  }

  try {
    await qrScanner.start();
    qrActive = true;
    document.getElementById("qrContainer").classList.remove("hidden");
    toggleQrButtons(true);
  } catch (err) {
    const message = err?.message ?? String(err);
    showError("apiError", `Camera access denied: ${message}`);
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

const apiNext = () => {
  const url = document.getElementById("apiUrl").value.trim();

  if (!url) {
    showError("apiError", "Please enter API URL");
    return;
  }

  dismissKeyboard();

  if (!isValidApiUrl(url)) {
    showError(
      "apiError",
      "Invalid API URL - must be https://eventsapi.chaturbate.com/events/... or https://events.testbed.cb.dev/events/...",
    );
    return;
  }

  state.apiUrl = url;
  hideElement("apiError");
  markStepComplete(STEPS.API);
  showConfirmation();
  showStep(STEPS.CONFIRM);
};

const showConfirmation = () => {
  document.getElementById("confirmSsid").textContent = state.ssid;

  const { username, isTestbed } = getApiUrlSummary(state.apiUrl);
  document.getElementById("confirmUsername").textContent =
    username || "(unknown)";
  document.getElementById("confirmTestbed").textContent = isTestbed
    ? "Yes"
    : "No";
};

const sendConfiguration = async () => {
  const btn = document.getElementById("confirmBtn");
  btn.disabled = true;

  try {
    console.log("Sending SSID...");
    await safeWrite(state.characteristics.ssid, state.ssid);
    await new Promise((r) => setTimeout(r, 150));

    console.log("Sending password...");
    await safeWrite(state.characteristics.password, state.password);
    await new Promise((r) => setTimeout(r, 150));

    console.log("Sending API URL...");
    await safeWrite(state.characteristics.apiUrl, state.apiUrl);
    await new Promise((r) => setTimeout(r, 150));

    console.log("Sending Save command...");
    await safeWrite(state.characteristics.wifiTest, "save");

    console.log("Configuration sent successfully");
    showConfigSuccess();
  } catch (err) {
    console.error("Error sending config:", err);
    console.error("Error name:", err.name);
    if (isGattDisconnect(err)) {
      console.log("Device disconnected after sending (may be expected)");
      showConfigSuccess();
    } else {
      showError("confirmError", `Failed to send config: ${err.message}`);
      btn.disabled = false;
    }
  }
};

// Event Listeners
document.getElementById("manualScanBtn").addEventListener("click", () => {
  showElement("scanSubtitle");
  showElement("scanLoading");
  hideElement("deviceContainer");
  startDeviceScan();
});

document.getElementById("wifiNextBtn").addEventListener("click", wifiNext);
document
  .getElementById("wifiBackBtn")
  .addEventListener("click", () => showStep(STEPS.DEVICE));

document.getElementById("scanQrBtn").addEventListener("click", startQrScan);
document.getElementById("stopQrBtn").addEventListener("click", stopQrScan);

document.getElementById("apiNextBtn").addEventListener("click", apiNext);
document
  .getElementById("apiBackBtn")
  .addEventListener("click", () => showStep(STEPS.WIFI));

document
  .getElementById("confirmBtn")
  .addEventListener("click", sendConfiguration);
document
  .getElementById("confirmBackBtn")
  .addEventListener("click", () => showStep(STEPS.API));

document.getElementById("rescanBtn").addEventListener("click", async () => {
  const btn = document.getElementById("rescanBtn");
  btn.disabled = true;
  btn.textContent = "Scanning...";

  try {
    document.getElementById("networksList").innerHTML =
      '<div class="network-empty">Scanning...</div>';
    if (state.characteristics.wifiTest) {
      await safeWrite(state.characteristics.wifiTest, "rescan");
    }
  } catch (err) {
    console.error("Rescan error:", err);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = "Rescan";
    }, 5000);
  }
});

// Lifecycle handlers
window.addEventListener("pagehide", () => stopQrScan(true));

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopQrScan(false);
  } else if (state.currentStep === STEPS.API && !qrActive) {
    toggleQrButtons(false);
  }
});

window.addEventListener("load", () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
});
