const STATUS_MAX_EM = 10;
const STATUS_MIN_PX = 1;

let soundEnabled = true;
let audioStarted = false;

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
  statusElement.style.whiteSpace = "nowrap";

  if (statusElement.scrollWidth > availableWidth) {
    const scale = availableWidth / statusElement.scrollWidth;
    const fittedFontSizePx = Math.max(STATUS_MIN_PX, Math.floor(maxFontSizePx * scale));
    statusElement.style.fontSize = `${fittedFontSizePx}px`;
  }

  statusElement.style.whiteSpace = "";
}

function setStatusHTML(html) {
  const statusElement = document.getElementById("status_par");
  if (!statusElement) {
    return;
  }

  if (statusElement.innerHTML === html) {
    return;
  }

  statusElement.innerHTML = html;
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
    showVaping(["Dev User"]);
  } else {
    showNobodyVaping();
  }
}

function getActiveVapers(devices) {
  const vapers = [];
  for (const [name, state] of Object.entries(devices || {})) {
    if (state.coil_a || state.coil_b) {
      vapers.push(name);
    }
  }
  return vapers;
}

setInterval(() => {
  if (devModeActive) return;

  fetch("/vape-status")
    .then(response => response.json())
    .then(data => {
      const vapers = getActiveVapers(data.devices);
      if (vapers.length > 0) {
        showVaping(vapers);
      } else {
        showNobodyVaping();
      }

      const debugElement = document.getElementById("debug_par");
      if (debugElement) debugElement.textContent = JSON.stringify(data);
    })
    .catch(error => {
        setStatusHTML("Failed to fetch vape status.");
    });
}, 100);

function tryStartAudio() {
  if (audioStarted) return;
  const audio = document.getElementById("bg-audio");
  if (!audio) return;
  audio.play().then(() => {
    audioStarted = true;
    updateAudioMute();
    document.removeEventListener("click", tryStartAudio);
    document.removeEventListener("touchstart", tryStartAudio);
    document.removeEventListener("keydown", tryStartAudio);
  }).catch(() => {});
}

document.addEventListener("click", tryStartAudio);
document.addEventListener("touchstart", tryStartAudio);
document.addEventListener("keydown", tryStartAudio);

const soundBtn = document.getElementById("btn-sound");
if (soundBtn) {
  soundBtn.addEventListener("click", () => {
    soundEnabled = !soundEnabled;
    if (soundEnabled) {
      soundBtn.textContent = "🔊";
      soundBtn.title = "Disable sound";
      soundBtn.setAttribute("aria-label", "Disable sound");
    } else {
      soundBtn.textContent = "🔇";
      soundBtn.title = "Enable sound";
      soundBtn.setAttribute("aria-label", "Enable sound");
    }
    updateAudioMute();
  });
}

function updateAudioMute() {
  const audio = document.getElementById("bg-audio");
  if (!audio) return;
  audio.muted = !soundEnabled || !currentlyVaping;
}

let currentlyVaping = false;
let fadeOutTimer = null;
let fadeOutAudioInterval = null;
const FADE_OUT_MS = 5000;

function cancelFadeOut() {
  if (fadeOutTimer !== null) {
    clearTimeout(fadeOutTimer);
    fadeOutTimer = null;
  }
  if (fadeOutAudioInterval !== null) {
    clearInterval(fadeOutAudioInterval);
    fadeOutAudioInterval = null;
  }
  const overlay = document.getElementById("rgb-overlay");
  const container = document.getElementById("gif-bounce-container");
  overlay.classList.remove("fading-out");
  container.classList.remove("fading-out");
}

function showVaping(names) {
  cancelFadeOut();
  const lines = names.map(n => `${n} chuffmaxxing`);
  setStatusHTML(lines.join("<br>"));
  const overlay = document.getElementById("rgb-overlay");
  overlay.classList.add("active");
  const container = document.getElementById("gif-bounce-container");
  container.style.opacity = "";
  startBouncingGifs();
  currentlyVaping = true;
  updateAudioMute();
  const audio = document.getElementById("bg-audio");
  if (audio) audio.volume = 1;
}

function showNobodyVaping() {
  if (!currentlyVaping && fadeOutTimer === null) {
    setStatusHTML("Nobody");
    return;
  }
  if (!currentlyVaping) return;

  setStatusHTML("Nobody");
  currentlyVaping = false;

  // Start fading out RGB overlay
  const overlay = document.getElementById("rgb-overlay");
  overlay.classList.add("fading-out");
  overlay.classList.remove("active");

  // Start fading out GIFs
  const container = document.getElementById("gif-bounce-container");
  container.classList.add("fading-out");

  // Fade out audio volume
  const audio = document.getElementById("bg-audio");
  if (audio && !audio.muted) {
    const fadeSteps = 50;
    const fadeInterval = FADE_OUT_MS / fadeSteps;
    const volumeStep = audio.volume / fadeSteps;
    fadeOutAudioInterval = setInterval(() => {
      if (audio.volume > volumeStep) {
        audio.volume -= volumeStep;
      } else {
        audio.volume = 0;
        clearInterval(fadeOutAudioInterval);
        fadeOutAudioInterval = null;
        audio.muted = true;
      }
    }, fadeInterval);
  }

  // After fade completes, clean up
  fadeOutTimer = setTimeout(() => {
    fadeOutTimer = null;
    stopBouncingGifs();
    overlay.classList.remove("fading-out");
    container.classList.remove("fading-out");
    if (audio) {
      audio.muted = true;
      audio.volume = 1;
    }
  }, FADE_OUT_MS);
}

// --- Bouncing GIFs ---
let bouncingGifs = [];
let bounceAnimationId = null;
let gifList = null;

const GIF_SIZE = 100;
const MIN_SPEED = 1;
const MAX_SPEED = 7;

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
