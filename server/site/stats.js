(function () {
    'use strict';

    var charts = {};
    var deviceSections = {};

    async function loadStats() {
        var res = await fetch('/stats/data');
        var data = await res.json();
        renderSummary(data);
        renderDevices(data.devices);
    }

    function renderSummary(data) {
        document.getElementById('stat-devices').textContent = data.device_count;
        document.getElementById('stat-chuffs-1h').textContent = data.chuffs_last_hour;
        document.getElementById('stat-chuffs-6h').textContent = data.chuffs_last_6_hours;
        document.getElementById('stat-chuffs-midnight').textContent = data.chuffs_since_midnight;
    }

    function renderDevices(devices) {
        var container = document.getElementById('devices-container');

        devices.forEach(function (device) {
            var cached = deviceSections[device.name];

            if (cached) {
                var statValues = cached.section.querySelectorAll('.stat-value');
                statValues[0].textContent = device.chuffs_last_hour;
                statValues[1].textContent = device.chuffs_last_6_hours;
                statValues[2].textContent = device.chuffs_since_midnight;

                renderChuffChart(cached.chuffCanvas, device.events_24h, parseInt(cached.windowSelect.value), device.name);
                renderDurationChart(cached.durationCanvas, device.events_24h, device.name);
                return;
            }

            var section = document.createElement('div');
            section.className = 'device-section';
            section.innerHTML =
                '<h2>' + escapeHtml(device.name) + '</h2>' +
                '<div class="stats-row">' +
                    '<div class="stat-card">' +
                        '<div class="stat-value">' + device.chuffs_last_hour + '</div>' +
                        '<div class="stat-label">Last Hour</div>' +
                    '</div>' +
                    '<div class="stat-card">' +
                        '<div class="stat-value">' + device.chuffs_last_6_hours + '</div>' +
                        '<div class="stat-label">Last 6 Hours</div>' +
                    '</div>' +
                    '<div class="stat-card">' +
                        '<div class="stat-value">' + device.chuffs_since_midnight + '</div>' +
                        '<div class="stat-label">Since Midnight UTC</div>' +
                    '</div>' +
                '</div>' +
                '<div class="card">' +
                    '<h3>Chuff Rate (Last 24h)</h3>' +
                    '<div class="chart-controls">' +
                        '<select class="window-select">' +
                            '<option value="1">1 minute</option>' +
                            '<option value="5" selected>5 minutes</option>' +
                            '<option value="15">15 minutes</option>' +
                            '<option value="30">30 minutes</option>' +
                            '<option value="60">60 minutes</option>' +
                        '</select>' +
                    '</div>' +
                    '<div class="chart-wrapper">' +
                        '<canvas class="chuff-chart"></canvas>' +
                    '</div>' +
                '</div>' +
                '<div class="card">' +
                    '<h3>Chuff Duration Distribution (Last 24h)</h3>' +
                    '<div class="chart-wrapper">' +
                        '<canvas class="duration-chart"></canvas>' +
                    '</div>' +
                '</div>';
            container.appendChild(section);

            var chuffCanvas = section.querySelector('.chuff-chart');
            var durationCanvas = section.querySelector('.duration-chart');
            var windowSelect = section.querySelector('.window-select');

            deviceSections[device.name] = {
                section: section,
                chuffCanvas: chuffCanvas,
                durationCanvas: durationCanvas,
                windowSelect: windowSelect,
            };

            renderChuffChart(chuffCanvas, device.events_24h, 5, device.name);
            renderDurationChart(durationCanvas, device.events_24h, device.name);

            windowSelect.addEventListener('change', function () {
                renderChuffChart(chuffCanvas, device.events_24h, parseInt(windowSelect.value), device.name);
            });
        });
    }

    function renderChuffChart(canvas, events, windowMinutes, deviceName) {
        var chartKey = 'chuff-' + deviceName;

        var now = new Date();
        var twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        var windowMs = windowMinutes * 60 * 1000;
        var bucketCount = Math.ceil(24 * 60 / windowMinutes);
        var buckets = [];
        var labels = [];

        for (var i = 0; i < bucketCount; i++) {
            buckets.push(0);
            var bucketStart = new Date(twentyFourHoursAgo.getTime() + i * windowMs);
            labels.push(bucketStart.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        }

        events.forEach(function (e) {
            if (e.event !== 'started') return;
            var t = new Date(e.timestamp);
            var idx = Math.floor((t.getTime() - twentyFourHoursAgo.getTime()) / windowMs);
            if (idx >= 0 && idx < bucketCount) buckets[idx]++;
        });

        var existing = charts[chartKey];
        if (existing) {
            existing.data.labels = labels;
            existing.data.datasets[0].data = buckets;
            existing.update();
            return;
        }

        var ctx = canvas.getContext('2d');
        charts[chartKey] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Chuffs',
                    data: buckets,
                    backgroundColor: 'rgba(255, 255, 255, 0.7)',
                    borderColor: '#fff',
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#999' } } },
                scales: {
                    x: {
                        ticks: { color: '#999', maxTicksLimit: 24 },
                        grid: { color: '#222' },
                    },
                    y: {
                        ticks: { color: '#999', stepSize: 1 },
                        grid: { color: '#222' },
                        beginAtZero: true,
                    },
                },
            },
        });
    }

    function renderDurationChart(canvas, events, deviceName) {
        var chartKey = 'duration-' + deviceName;

        var durations = [];
        var pending = {};

        events.forEach(function (e) {
            if (e.event === 'started') {
                pending[e.coil] = new Date(e.timestamp).getTime();
            } else if (e.event === 'stopped' && pending[e.coil] !== undefined) {
                var duration = (new Date(e.timestamp).getTime() - pending[e.coil]) / 1000;
                if (duration > 0 && duration < 300) durations.push(duration);
                delete pending[e.coil];
            }
        });

        var binSize = 0.5;
        var bins = [];
        var labels = [];

        if (durations.length > 0) {
            var maxDuration = Math.min(Math.ceil(Math.max.apply(null, durations) / binSize) * binSize, 30);
            var binCount = Math.ceil(maxDuration / binSize);
            for (var i = 0; i < binCount; i++) {
                bins.push(0);
                labels.push((i * binSize).toFixed(1) + 's');
            }
            durations.forEach(function (d) {
                var idx = Math.min(Math.floor(d / binSize), binCount - 1);
                bins[idx]++;
            });
        }

        var existing = charts[chartKey];
        if (existing) {
            existing.data.labels = labels;
            existing.data.datasets[0].data = bins;
            existing.options.plugins.title.display = durations.length === 0;
            existing.update();
            return;
        }

        var ctx = canvas.getContext('2d');
        charts[chartKey] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Frequency',
                    data: bins,
                    backgroundColor: 'rgba(255, 255, 255, 0.5)',
                    borderColor: '#ccc',
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: durations.length === 0, text: 'No chuff duration data available', color: '#666' },
                    legend: { labels: { color: '#999' } },
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Duration', color: '#999' },
                        ticks: { color: '#999' },
                        grid: { color: '#222' },
                    },
                    y: {
                        title: { display: true, text: 'Count', color: '#999' },
                        ticks: { color: '#999', stepSize: 1 },
                        grid: { color: '#222' },
                        beginAtZero: true,
                    },
                },
            },
        });
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    var refreshTimer = null;

    function scheduleRefresh() {
        if (refreshTimer) return;
        refreshTimer = setTimeout(function () {
            refreshTimer = null;
            loadStats();
        }, 500);
    }

    function connectStream() {
        var source = new EventSource('/stats/stream');
        source.onmessage = function () {
            scheduleRefresh();
        };
    }

    loadStats();
    connectStream();
})();
