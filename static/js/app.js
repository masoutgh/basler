document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const cameraListView = document.getElementById('camera-list-view');
    const cameraDetailView = document.getElementById('camera-detail-view');
    const cameraListContainer = document.getElementById('camera-list-container');
    const scanButton = document.getElementById('scan-button');
    const backButton = document.getElementById('back-to-list-button');
    
    let activeWebSocket = null;

    // --- UTILITY ---
    const getCsrfToken = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    // --- API FUNCTIONS ---
    const api = {
        fetchCameras: () => fetch('/api/cameras/'),
        scan: () => fetch('/api/cameras/scan/', { method: 'POST', headers: {'X-CSRFToken': getCsrfToken()} }),
        fetchCameraDetails: (sn) => fetch(`/api/cameras/${sn}/`),
        fetchCameraFeatures: (sn) => fetch(`/api/cameras/${sn}/features/`),
        applyProfile: (id) => fetch(`/api/profiles/${id}/apply/`, { method: 'POST', headers: {'X-CSRFToken': getCsrfToken()} }),
        saveProfile: (sn, name) => fetch(`/api/cameras/${sn}/save_profile/`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken()},
            body: JSON.stringify({ name: name })
        }),
    };

    // --- RENDER FUNCTIONS ---
    const renderCameraList = (cameras) => {
        cameraListContainer.innerHTML = '';
        if (cameras.length === 0) {
            cameraListContainer.innerHTML = '<div class="list-group-item">No cameras found. Try scanning.</div>';
            return;
        }
        cameras.forEach(camera => {
            const statusClass = camera.status === 'Online' ? 'bg-success' : 'bg-secondary';
            const cameraEl = document.createElement('a');
            cameraEl.href = '#';
            cameraEl.className = 'list-group-item list-group-item-action';
            cameraEl.dataset.serial = camera.serial_number;
            cameraEl.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${camera.friendly_name || camera.model_name}</strong>
                        <small class="text-muted d-block">SN: ${camera.serial_number}</small>
                    </div>
                    <span class="badge rounded-pill ${statusClass}">${camera.status}</span>
                </div>
            `;
            cameraEl.addEventListener('click', (e) => {
                e.preventDefault();
                showDetailView(camera.serial_number);
            });
            cameraListContainer.appendChild(cameraEl);
        });
    };

    const renderCameraDetail = (camera, featuresData) => {
        document.getElementById('camera-detail-title').textContent = camera.friendly_name || camera.model_name;
        
        const controlsContainer = document.getElementById('controls-container');
        const isOnline = featuresData.status === 'online';
        let featuresHtml = '';

        if (featuresData.message) {
            const alertClass = isOnline ? 'alert-info' : 'alert-warning';
            featuresHtml += `<div class="alert ${alertClass}">${featuresData.message}</div>`;
        }

        if (featuresData.features && featuresData.features.length > 0) {
            featuresHtml += featuresData.features.map(f => `<div class="mb-2"><label class="form-label">${f.name}</label><p class="form-text m-0">Value: ${f.value}</p></div>`).join('');
        }

        let profilesHtml = camera.profiles.map(p => `
            <li class="list-group-item d-flex justify-content-between align-items-center">
                ${p.name}
                <button class="btn btn-sm btn-primary apply-profile-btn" data-profile-id="${p.id}" ${!isOnline ? 'disabled' : ''}>Apply</button>
            </li>`).join('');

        controlsContainer.innerHTML = `
            <div class="card mb-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span>Settings</span>
                    <span class="badge bg-${isOnline ? 'success' : 'danger'}">${isOnline ? 'Online' : 'Offline'}</span>
                </div>
                <div class="card-body" style="max-height: 300px; overflow-y: auto;">${featuresHtml}</div>
            </div>
            <div class="card">
                <div class="card-header">Configuration Profiles</div>
                <form id="save-profile-form" class="card-body" ${!isOnline ? 'hidden' : ''}>
                    <div class="input-group">
                        <input type="text" name="profile_name" class="form-control" placeholder="New Profile Name" required>
                        <button class="btn btn-outline-success" type="submit">Save Current Settings</button>
                    </div>
                </form>
                <ul class="list-group list-group-flush">${profilesHtml || '<li class="list-group-item text-muted">No saved profiles.</li>'}</ul>
            </div>
        `;

        document.querySelectorAll('.apply-profile-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const profileId = btn.dataset.profileId;
                await api.applyProfile(profileId);
                alert('Profile applied!');
                showDetailView(camera.serial_number);
            });
        });

        const saveProfileForm = document.getElementById('save-profile-form');
        if (saveProfileForm) {
            saveProfileForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const profileName = e.target.elements.profile_name.value;
                if (profileName) {
                    const response = await api.saveProfile(camera.serial_number, profileName);
                    if (response.ok) {
                        alert('Profile saved!');
                        showDetailView(camera.serial_number);
                    } else {
                        const error = await response.json();
                        alert(`Error saving profile: ${error.error}`);
                    }
                }
            });
        }
    };


    const showListView = async () => {
        cameraDetailView.classList.add('d-none');
        cameraListView.classList.remove('d-none');
        try {
            const response = await api.fetchCameras();
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            const cameras = await response.json();
            renderCameraList(cameras);
        } catch (error) {
            console.error("Failed to fetch camera list:", error);
            cameraListContainer.innerHTML = `<div class="alert alert-danger">Error: Could not load camera list. Is the server running?</div>`;
        }
    };

    const showDetailView = async (serialNumber) => {
        cameraListView.classList.add('d-none');
        cameraDetailView.classList.remove('d-none');

        const [detailsRes, featuresRes] = await Promise.all([
            api.fetchCameraDetails(serialNumber),
            api.fetchCameraFeatures(serialNumber)
        ]);

        const camera = await detailsRes.json();
        const featuresData = await featuresRes.json();

        renderCameraDetail(camera, featuresData);

        const videoElement = document.getElementById('video-stream');
        if (featuresData.status === 'online') {
            videoElement.alt = "Connecting to live feed...";
            startVideoStream(serialNumber);
        } else {
            if (activeWebSocket) activeWebSocket.close();
            videoElement.src = '';
            videoElement.alt = "Camera is offline. No live feed available.";
        }
    };

const startVideoStream = (serialNumber) => {
    if (activeWebSocket) {
        activeWebSocket.close();
    }
    
    const videoElement = document.getElementById('video-stream');
    const socketUrl = `ws://${window.location.host}/ws/camera_stream/${serialNumber}/`;
    
    console.log(`[WebSocket] Attempting to connect to: ${socketUrl}`);
    activeWebSocket = new WebSocket(socketUrl);

    activeWebSocket.onopen = (event) => {
        console.log("[WebSocket] Connection opened successfully!");
        videoElement.alt = "Live feed established. Waiting for frames...";
    };

    activeWebSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.image) {
            videoElement.src = `data:image/jpeg;base64,${data.image}`;
        }
    };

    activeWebSocket.onerror = (error) => {
        console.error("[WebSocket] Error occurred:", error);
        videoElement.alt = "A WebSocket error occurred. See browser console for details.";
    };

    activeWebSocket.onclose = (event) => {
        console.log(`[WebSocket] Connection closed. Code: ${event.code}, Reason: ${event.reason}`);
        if (!event.wasClean) {
            videoElement.alt = "Connection lost unexpectedly. Please refresh.";
        }
    };
};
    // --- INITIALIZATION ---
    scanButton.addEventListener('click', async () => {
        scanButton.textContent = 'Scanning...';
        scanButton.disabled = true;
        await api.scan();
        await showListView();
        scanButton.textContent = 'Scan for Cameras';
        scanButton.disabled = false;
    });

    backButton.addEventListener('click', () => {
        if (activeWebSocket) activeWebSocket.close();
        showListView();
    });

    showListView();
});