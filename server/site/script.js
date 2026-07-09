const STATUS_MAX_EM = 10;
const STATUS_MIN_PX = 1;

let devModeActive = false;
let devVapeState = false;
let devModeAvailable = false;

function fitStatusText() {
  const statusElement = document.getElementById("status_par");
  if (!statusElement || !statusElement.parentElement) {
    return;
  }

  const rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
  const maxFontSizePx = rootFontSize * STATUS_MAX_EM;
  const availableWidth = statusElement.parentElement.clientWidth;

  if (availableWidth <= 0) {
    return;
  }

  statusElement.style.fontSize = `${maxFontSizePx}px`;

  if (statusElement.scrollWidth > availableWidth) {
    const scale = availableWidth / statusElement.scrollWidth;
    const fittedFontSizePx = Math.max(STATUS_MIN_PX, Math.floor(maxFontSizePx * scale));
    statusElement.style.fontSize = `${fittedFontSizePx}px`;
  }
}

function setStatusText(text) {
  const statusElement = document.getElementById("status_par");
  if (!statusElement) {
    return;
  }

  if (statusElement.textContent === text) {

    return;

  }

  statusElement.textContent = text;
  fitStatusText();
}

window.addEventListener("resize", fitStatusText);

// Check if dev mode is available from server
fetch("/dev-config")
  .then(response => response.json())
  .then(data => {
    if (data.dev_mode) {
      devModeAvailable = true;
      const controls = document.getElementById("dev-controls");
      if (controls) controls.style.display = "flex";
      initDevControls();
    }
  })
  .catch(() => {});

function initDevControls() {
  const btnDev = document.getElementById("btn-dev-mode");
  const btnToggle = document.getElementById("btn-toggle-state");

  btnDev.addEventListener("click", () => {
    devModeActive = !devModeActive;
    btnDev.textContent = `Dev Mode: ${devModeActive ? "ON" : "OFF"}`;
    btnToggle.disabled = !devModeActive;
    if (devModeActive) {
      applyDevState();
    }
  });

  btnToggle.addEventListener("click", () => {
    devVapeState = !devVapeState;
    applyDevState();
  });
}

function applyDevState() {
  if (devVapeState) {
    chrisIsVaping();
  } else {
    chrisIsNotVaping();
  }
}

setInterval(() => {
  if (devModeActive) return;

  fetch("/vape-status")
    .then(response => response.json())
    .then(data => {
      let isVaping = data.is_vaping;
      if (isVaping) {
        chrisIsVaping();
      } else {
        chrisIsNotVaping();
      }

      const debugElement = document.getElementById("debug_par");
      if (debugElement) debugElement.textContent = JSON.stringify(data);
    })
    .catch(error => {
        setStatusText("Failed to fetch vape status.");
    });
}, 100);

function chrisIsVaping() {
  const statusText = "Yep";
  setStatusText(statusText);
  document.getElementById("rgb-overlay").classList.add("active");
}

function chrisIsNotVaping() {
  const statusText = "Nope";
  setStatusText(statusText);
  document.getElementById("rgb-overlay").classList.remove("active");
}
