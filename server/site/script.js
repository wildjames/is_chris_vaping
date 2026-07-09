const STATUS_MAX_EM = 10;
const STATUS_MIN_PX = 1;

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

window.addEventListener("resize", fitStatusText);

setInterval(() => {
  fetch("/vape-status")
    .then(response => response.json())
    .then(data => {
      let isVaping = data.is_vaping;
      if (isVaping) {
        chrisIsVaping()
      } else {
      const debugElement = document.getElementById("debug_par");
      if (debugElement) debugElement.textContent = JSON.stringify(data);
      }

      document.getElementById("debug_par").textContent = JSON.stringify(data);
    })
    .catch(error => {
        setStatusText("Failed to fetch vape status.");
    });
}, 100);

function chrisIsVaping() {
  const statusText = "Yep";
  setStatusText(statusText);
}

function chrisIsNotVaping() {
  const statusText = "Nope";
  setStatusText(statusText);
}
