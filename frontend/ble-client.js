// BLE Constants
const SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
const CHAR_UUIDS = {
  ssid: "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
  password: "6e400003-b5a3-f393-e0a9-e50e24dcca9e",
  apiUrl: "6e400004-b5a3-f393-e0a9-e50e24dcca9e",
  status: "6e400005-b5a3-f393-e0a9-e50e24dcca9e",
  networks: "6e400006-b5a3-f393-e0a9-e50e24dcca9e",
  wifiTest: "6e400007-b5a3-f393-e0a9-e50e24dcca9e",
};

// Protocol Constants
const CHUNK_SIZE = 18;
const CHUNK_DELAY_MS = 50;

// Text Encoding
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

export class BleClient {
  constructor() {
    this.device = null;
    this.server = null;
    this.characteristics = {};
    this.notifications = {};
    this.eventListeners = {};
  }

  /**
   * Decode GATT value to string
   * @param {DataView|ArrayBuffer} value
   */
  static decodeValue(value) {
    if (!value) return "";
    if (value instanceof DataView) {
      return textDecoder.decode(
        new Uint8Array(value.buffer, value.byteOffset, value.byteLength),
      );
    }
    if (value instanceof ArrayBuffer) {
      return textDecoder.decode(new Uint8Array(value));
    }
    return textDecoder.decode(value);
  }

  /**
   * Listen for events (status, networks, etc)
   * @param {string} event
   * @param {function} callback
   */
  on(event, callback) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  emit(event, data) {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach((cb) => cb(data));
    }
  }

  async scan() {
    if (!navigator.bluetooth) {
      throw new Error("Bluetooth not supported");
    }

    this.device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: "StripAlerts-" }],
      optionalServices: [SERVICE_UUID],
    });

    this.device.addEventListener("gattserverdisconnected", () => {
      this.emit("disconnected");
    });

    return this.device;
  }

  async connect() {
    if (!this.device) throw new Error("No device selected");

    if (this.device.gatt.connected && this.server) return;

    console.log("Connecting GATT...");
    this.server = await this.device.gatt.connect();
    const service = await this.server.getPrimaryService(SERVICE_UUID);

    for (const [key, uuid] of Object.entries(CHAR_UUIDS)) {
      this.characteristics[key] = await service.getCharacteristic(uuid);
    }

    // Setup notifications
    await this._enableNotification("status", (e) => {
      const val = BleClient.decodeValue(e.target.value);
      this.emit("status", val);
    });

    await this._enableNotification("networks", (e) => {
      const val = BleClient.decodeValue(e.target.value);
      try {
        this.emit("networks", JSON.parse(val));
      } catch (e) {
        console.error("Invalid networks JSON", e);
      }
    });

    await this._enableNotification("wifiTest", (e) => {
      const val = BleClient.decodeValue(e.target.value);
      this.emit("wifiTest", val);
    });
  }

  async _enableNotification(key, handler) {
    if (!this.characteristics[key]) return;
    try {
      await this.characteristics[key].startNotifications();
      this.characteristics[key].addEventListener(
        "characteristicvaluechanged",
        handler,
      );
      this.notifications[key] = true;
    } catch (e) {
      console.warn(`Failed to enable ${key} notifications`, e);
    }
  }

  async write(key, text) {
    const char = this.characteristics[key];
    if (!char) throw new Error(`Characteristic ${key} not found`);

    const allBytes = textEncoder.encode(text || "");

    // Empty payload
    if (allBytes.length === 0) {
      // Send clear command [0x01]
      await this._writeRaw(char, new Uint8Array([0x01]));
      return;
    }

    const chunks = [];
    let offset = 0;

    // Utf8 safe chunking
    while (offset < allBytes.length) {
      let end = Math.min(offset + CHUNK_SIZE, allBytes.length);
      while (end > offset && (allBytes[end - 1] & 0xc0) === 0x80) {
        end--;
      }

      if (end === offset) {
        end = Math.min(offset + CHUNK_SIZE, allBytes.length);
      }

      chunks.push(allBytes.subarray(offset, end));
      offset = end;
    }

    // Send chunks
    for (let i = 0; i < chunks.length; i++) {
      const isFirst = i === 0;
      const payload = new Uint8Array(chunks[i].length + 1);
      payload[0] = isFirst ? 0x01 : 0x02; // 0x01 = Start/Overwrite, 0x02 = Append
      payload.set(chunks[i], 1);

      await this._writeRaw(char, payload);

      if (i < chunks.length - 1) {
        await new Promise((r) => setTimeout(r, CHUNK_DELAY_MS));
      }
    }
  }

  async _writeRaw(char, payload) {
    try {
      await char.writeValue(payload);
    } catch (err) {
      // Simple retry logic could go here, or bubble up
      throw err;
    }
  }

  async read(key) {
    const char = this.characteristics[key];
    if (!char) throw new Error(`Characteristic ${key} not found`);
    const val = await char.readValue();
    return BleClient.decodeValue(val);
  }
}
