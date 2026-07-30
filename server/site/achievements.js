(function () {
    'use strict';

    var filterSelect = document.getElementById('device-filter');
    var grid = document.getElementById('achievements-grid');
    var unlockedCount = document.getElementById('unlocked-count');
    var totalCount = document.getElementById('total-count');

    function loadDevices() {
        fetch('/stats/data')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                data.devices.forEach(function (d) {
                    var opt = document.createElement('option');
                    opt.value = d.name;
                    opt.textContent = d.name;
                    filterSelect.appendChild(opt);
                });
            })
            .catch(function () {});
    }

    function loadAchievements() {
        var device = filterSelect.value;
        var url = '/achievements/all';
        if (device) url += '?device=' + encodeURIComponent(device);

        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (achievements) { render(achievements, device); })
            .catch(function () {});
    }

    function render(achievements, deviceFilter) {
        var unlocked = 0;
        var html = '';

        achievements.forEach(function (ach) {
            var isUnlocked = ach.awarded.length > 0;
            if (isUnlocked) unlocked++;

            var awardsHtml = '';
            if (isUnlocked) {
                ach.awarded.forEach(function (a) {
                    var device = a.device_name || 'Global';
                    var date = new Date(a.awarded_at).toLocaleDateString();
                    awardsHtml += '<div class="award-entry"><span class="award-device">' +
                        escapeHtml(device) + '</span> — ' + date + '</div>';
                });
            }

            html += '<div class="achievement-card ' + (isUnlocked ? 'unlocked' : 'locked') + '">' +
                '<div class="ach-header">' +
                    '<span class="ach-icon">' + (isUnlocked ? '🏆' : '🔒') + '</span>' +
                    '<span class="ach-name">' + escapeHtml(ach.name) + '</span>' +
                '</div>' +
                '<div class="ach-description">' + escapeHtml(ach.description) + '</div>' +
                (awardsHtml ? '<div class="ach-awards">' + awardsHtml + '</div>' : '') +
            '</div>';
        });

        grid.innerHTML = html;
        unlockedCount.textContent = unlocked;
        totalCount.textContent = achievements.length;
    }

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    filterSelect.addEventListener('change', loadAchievements);
    loadDevices();
    loadAchievements();
})();
