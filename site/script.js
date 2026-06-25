setInterval(() => {
  fetch("http://localhost:5000/vape-status")
    .then(response => response.json())
    .then(data => {
      let isVaping = data.is_vaping;
      if (isVaping) {
        chrisIsVaping()
      } else {
        chrisIsNotVaping()
      }

      document.getElementById("debug_par").textContent = JSON.stringify(data);
    })
    .catch(error => {
        document.getElementById("status_par").textContent = "Failed to fetch vape status.";
    });
}, 100);

function chrisIsVaping() {
  statusText = "Yep";
  document.getElementById("status_par").textContent = statusText;
}

function chrisIsNotVaping() {
  statusText = "Nope";
  document.getElementById("status_par").textContent = statusText;
}
