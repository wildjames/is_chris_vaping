(function () {
    'use strict';

    let activityChart = null;
    let deviceChart = null;

    // --- Auth ---

    async function checkAuth() {
        const res = await fetch('/admin/check');
        const data = await res.json();
        if (data.authenticated) {
            showDashboard();
        }
    }

    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = document.getElementById('password-input').value;
        const res = await fetch('/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });
        if (res.ok) {
            document.getElementById('login-error').textContent = '';
            showDashboard();
        } else {
            const data = await res.json();
            document.getElementById('login-error').textContent = data.error || 'Login failed';
        }
    });

    document.getElementById('logout-btn').addEventListener('click', async () => {
        await fetch('/admin/logout', { method: 'POST' });
        document.getElementById('dashboard').classList.remove('active');
        document.getElementById('login-container').classList.remove('hidden');
    });

    function showDashboard() {
        document.getElementById('login-container').classList.add('hidden');
        document.getElementById('dashboard').classList.add('active');
        loadDashboard();
    }

    // --- Dashboard Data ---

    async function loadDashboard() {
        await Promise.all([loadDevices(), loadActivity()]);
    }

    async function loadDevices() {
        const res = await fetch('/admin/devices');
        if (res.status === 401) {
            document.getElementById('dashboard').classList.remove('active');
            document.getElementById('login-container').classList.remove('hidden');
            return;
        }
        const data = await res.json();
        const devices = data.devices;

        document.getElementById('stat-devices').textContent = devices.length;
        const activeCount = devices.filter(d => d.coil_a || d.coil_b).length;
        document.getElementById('stat-active').textContent = activeCount;

        // Populate device filter
        const select = document.getElementById('chart-device');
        const currentVal = select.value;
        select.innerHTML = '<option value="">All Devices</option>';
        devices.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.name;
            opt.textContent = d.name;
            if (d.name === currentVal) opt.selected = true;
            select.appendChild(opt);
        });

        // Render table
        const tbody = document.getElementById('device-tbody');
        tbody.innerHTML = '';
        devices.forEach(d => {
            const isActive = d.coil_a || d.coil_b;
            const lastUpdated = d.last_updated
                ? new Date(d.last_updated).toLocaleString()
                : 'Never';
            const tr = document.createElement('tr');
            tr.innerHTML =
                '<td><span class="status-dot ' + (isActive ? 'active' : 'inactive') + '"></span>' + (isActive ? 'Active' : 'Idle') + '</td>' +
                '<td><strong>' + escapeHtml(d.name) + '</strong></td>' +
                '<td>' + escapeHtml(d.last_event || '-') + '</td>' +
                '<td>' + lastUpdated + '</td>' +
                '<td>' + d.event_count + '</td>' +
                '<td>' +
                    '<button class="btn-view" data-id="' + d.id + '">Events</button>' +
                    '<button class="btn-delete" data-id="' + d.id + '">Delete</button>' +
                '</td>';
            tr.querySelector('.btn-view').dataset.name = d.name;
            tr.querySelector('.btn-delete').dataset.name = d.name;
            tbody.appendChild(tr);
        });

        // Attach event handlers via delegation
        tbody.querySelectorAll('.btn-view').forEach(btn => {
            btn.addEventListener('click', () => viewEvents(btn.dataset.id, btn.dataset.name));
        });
        tbody.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', () => deleteDevice(btn.dataset.id, btn.dataset.name));
        });
    }

    async function loadActivity() {
        const days = document.getElementById('chart-days').value;
        const device = document.getElementById('chart-device').value;
        let url = '/admin/activity?days=' + days;
        if (device) url += '&device=' + encodeURIComponent(device);

        const res = await fetch(url);
        if (res.status === 401) return;
        const data = await res.json();

        document.getElementById('stat-events-total').textContent = data.total_events;

        const today = new Date().toISOString().split('T')[0];
        const todayData = data.daily[today];
        document.getElementById('stat-events-today').textContent =
            todayData ? (todayData.started + todayData.stopped) : 0;

        renderActivityChart(data, days);
        renderDeviceChart(data);
    }

    function renderActivityChart(data, days) {
        const ctx = document.getElementById('activity-chart').getContext('2d');
        const useHourly = days <= 2;
        const chartData = useHourly ? data.hourly : data.daily;

        const labels = Object.keys(chartData).sort();
        const started = labels.map(k => chartData[k].started || 0);
        const stopped = labels.map(k => chartData[k].stopped || 0);

        const displayLabels = labels.map(l => {
            if (useHourly) return l.split(' ')[1] || l;
            return l.substring(5);
        });

        if (activityChart) activityChart.destroy();
        activityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: displayLabels,
                datasets: [
                    {
                        label: 'Started',
                        data: started,
                        backgroundColor: 'rgba(76, 175, 80, 0.7)',
                        borderColor: '#4caf50',
                        borderWidth: 1,
                    },
                    {
                        label: 'Stopped',
                        data: stopped,
                        backgroundColor: 'rgba(233, 69, 96, 0.7)',
                        borderColor: '#e94560',
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#aaa' } } },
                scales: {
                    x: { ticks: { color: '#aaa' }, grid: { color: '#333' } },
                    y: { ticks: { color: '#aaa' }, grid: { color: '#333' }, beginAtZero: true },
                },
            },
        });
    }

    function renderDeviceChart(data) {
        const ctx = document.getElementById('device-chart').getContext('2d');
        const deviceNames = Object.keys(data.per_device);
        const startedCounts = deviceNames.map(d => data.per_device[d].started || 0);

        if (deviceChart) deviceChart.destroy();
        deviceChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: deviceNames,
                datasets: [{
                    data: startedCounts,
                    backgroundColor: [
                        '#e94560', '#4caf50', '#2196f3', '#ff9800', '#9c27b0',
                        '#00bcd4', '#ffeb3b', '#795548',
                    ],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#aaa' }, position: 'right' } },
            },
        });
    }

    // --- Actions ---

    async function deleteDevice(id, name) {
        if (!confirm('Delete device "' + name + '" and all its events? This cannot be undone.')) return;
        const res = await fetch('/admin/devices/' + id, { method: 'DELETE' });
        if (res.ok) {
            loadDashboard();
        } else {
            const data = await res.json();
            alert(data.error || 'Failed to delete device');
        }
    }

    async function viewEvents(id, name) {
        document.getElementById('modal-title').textContent = 'Events: ' + name;
        const res = await fetch('/admin/devices/' + id + '/events?limit=50');
        if (!res.ok) return;
        const data = await res.json();

        const list = document.getElementById('events-list');
        list.innerHTML = '';
        if (data.events.length === 0) {
            list.innerHTML = '<li>No events recorded</li>';
        } else {
            data.events.forEach(e => {
                const li = document.createElement('li');
                const time = new Date(e.timestamp).toLocaleString();
                li.innerHTML =
                    '<span class="event-' + e.event + '">' + e.coil + ' ' + e.event + '</span>' +
                    '<span class="event-time">' + time + '</span>';
                list.appendChild(li);
            });
        }
        document.getElementById('events-modal').classList.add('active');
    }

    document.getElementById('modal-close').addEventListener('click', () => {
        document.getElementById('events-modal').classList.remove('active');
    });

    document.getElementById('events-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            e.currentTarget.classList.remove('active');
        }
    });

    // Chart controls
    document.getElementById('chart-days').addEventListener('change', loadActivity);
    document.getElementById('chart-device').addEventListener('change', loadActivity);
    document.getElementById('chart-refresh').addEventListener('click', loadDashboard);

    // --- Utils ---

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Auto-refresh every 30s
    setInterval(() => {
        if (document.getElementById('dashboard').classList.contains('active')) {
            loadDashboard();
        }
    }, 30000);

    // Init
    checkAuth();
})();
