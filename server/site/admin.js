(function () {
    'use strict';

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
        loadDevices();
    }

    // --- Dashboard Data ---

    async function loadDevices() {
        const res = await fetch('/admin/devices');
        if (res.status === 401) {
            document.getElementById('dashboard').classList.remove('active');
            document.getElementById('login-container').classList.remove('hidden');
            return;
        }
        const data = await res.json();
        const devices = data.devices;

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

    // --- Actions ---

    async function deleteDevice(id, name) {
        if (!confirm('Delete device "' + name + '" and all its events? This cannot be undone.')) return;
        const res = await fetch('/admin/devices/' + id, { method: 'DELETE' });
        if (res.ok) {
            loadDevices();
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

    // --- Utils ---

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Auto-refresh every 30s
    setInterval(() => {
        if (document.getElementById('dashboard').classList.contains('active')) {
            loadDevices();
        }
    }, 30000);

    // Init
    checkAuth();
})();
