const STATUS_MAX_EM = 10;
const STATUS_MIN_PX = 1;

let soundEnabled = false;

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

document.getElementById("btn-sound").addEventListener("click", () => {
  const audio = document.getElementById("bg-audio");
  const btn = document.getElementById("btn-sound");
  soundEnabled = !soundEnabled;
  if (soundEnabled) {
    audio.play();
    btn.textContent = "🔊";
    btn.title = "Disable sound";
  } else {
    btn.textContent = "🔇";
    btn.title = "Enable sound";
  }
  updateAudioMute();
});

function updateAudioMute() {
  const audio = document.getElementById("bg-audio");
  audio.muted = !soundEnabled || !currentlyVaping;
}

let currentlyVaping = false;

function chrisIsVaping() {
  const statusText = "Yep";
  setStatusText(statusText);
  document.getElementById("rgb-overlay").classList.add("active");
  startBouncingGifs();
  currentlyVaping = true;
  updateAudioMute();
}

function chrisIsNotVaping() {
  const statusText = "Nope";
  setStatusText(statusText);
  document.getElementById("rgb-overlay").classList.remove("active");
  stopBouncingGifs();
  currentlyVaping = false;
  updateAudioMute();
}

// --- Bouncing GIFs ---
let bouncingGifs = [];
let bounceAnimationId = null;
let gifList = null;

const GIF_SIZE = 100;
const MIN_SPEED = 1;
const MAX_SPEED = 4;

async function loadGifList() {
  if (gifList !== null) return gifList;
  try {
    const response = await fetch("/gifs/manifest.json");
    const data = await response.json();
    gifList = data || [];
  } catch {
    gifList = [];
  }
  return gifList;
}

function randomSpeed() {
  const speed = MIN_SPEED + Math.random() * (MAX_SPEED - MIN_SPEED);
  return Math.random() < 0.5 ? speed : -speed;
}

async function startBouncingGifs() {
  if (bounceAnimationId !== null) return;

  const gifs = await loadGifList();
  if (gifs.length === 0) return;

  const container = document.getElementById("gif-bounce-container");
  container.style.display = "block";

  for (const gif of gifs) {
    const img = document.createElement("img");
    img.src = `/gifs/${gif}`;
    img.className = "bouncing-gif";
    img.style.width = `${GIF_SIZE}px`;
    img.style.height = `${GIF_SIZE}px`;

    const x = Math.random() * (window.innerWidth - GIF_SIZE);
    const y = Math.random() * (window.innerHeight - GIF_SIZE);

    img.style.left = `${x}px`;
    img.style.top = `${y}px`;
    container.appendChild(img);

    bouncingGifs.push({ el: img, x, y, vx: randomSpeed(), vy: randomSpeed() });
  }

  bounceAnimationId = requestAnimationFrame(animateBounce);
}

function stopBouncingGifs() {
  if (bounceAnimationId !== null) {
    cancelAnimationFrame(bounceAnimationId);
    bounceAnimationId = null;
  }
  const container = document.getElementById("gif-bounce-container");
  container.style.display = "none";
  container.innerHTML = "";
  bouncingGifs = [];
}

function animateBounce() {
  const w = window.innerWidth;
  const h = window.innerHeight;

  for (const gif of bouncingGifs) {
    gif.x += gif.vx;
    gif.y += gif.vy;

    if (gif.x <= 0) { gif.x = 0; gif.vx = Math.abs(gif.vx); }
    if (gif.x >= w - GIF_SIZE) { gif.x = w - GIF_SIZE; gif.vx = -Math.abs(gif.vx); }
    if (gif.y <= 0) { gif.y = 0; gif.vy = Math.abs(gif.vy); }
    if (gif.y >= h - GIF_SIZE) { gif.y = h - GIF_SIZE; gif.vy = -Math.abs(gif.vy); }

    gif.el.style.left = `${gif.x}px`;
    gif.el.style.top = `${gif.y}px`;
  }

  bounceAnimationId = requestAnimationFrame(animateBounce);
}
