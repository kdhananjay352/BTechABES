/**
 * ============================================================================
 * COMMON JAVASCRIPT UTILITIES
 * This file contains global helper functions used across the entire application,
 * such as Toast notifications, file upload handling, date initialization, and 
 * responsive menu toggles.
 * ============================================================================
 */

(function () {
    "use strict";

    /**
     * ------------------------------------------------------------------------
     * 1. TOAST NOTIFICATION SYSTEM
     * ------------------------------------------------------------------------
     * Creates and manages the container that holds the popup notifications.
     * Ensures toasts float above the footer and action buttons.
     */
    function createToastContainer() {
        let container = document.getElementById("toastContainer");
        if (!container) {
            container = document.createElement("div");
            container.id = "toastContainer";
            container.className = "position-fixed end-0 p-3";
            container.style.zIndex = "1110";

            // place the toast container above the footer by footer height
            const footer = document.querySelector('footer');
            const footerHeight = footer ? (footer.offsetHeight || 0) : 0;
            container.style.bottom = footerHeight ? (footerHeight + 12) + 'px' : '1rem';

            document.body.appendChild(container);

            // update position on resize in case footer height changes
            window.addEventListener('resize', function () {
                const f = document.querySelector('footer');
                const h = f ? (f.offsetHeight || 0) : 0;
                container.style.bottom = h ? (h + 12) + 'px' : '1rem';
            });
        } else {
            // ensure expected classes and z-index
            container.classList.add('position-fixed', 'end-0', 'p-3');
            try { container.style.zIndex = '1110'; } catch (e) { }
            const footer = document.querySelector('footer');
            const footerHeight = footer ? (footer.offsetHeight || 0) : 0;
            container.style.bottom = footerHeight ? (footerHeight + 12) + 'px' : '1rem';
        }

        return container;
    }

    /**
     * Displays a dynamic popup notification (Toast).
     * Automatically maps backend statuses (success, danger, warning, info) 
     * to the correct colors and icons.
     */
    window.showToast = function (
        message,
        title = "",
        type = "info", // Default is info
        autohide = true,
        delay = 4000,
    ) {
        const container = createToastContainer();
        if (!container) return;

        // Dynamic Icon Logic mapping backend status to UI icons
        let iconClass = "fa-solid fa-circle-info text-primary fa-lg"; // Default Blue Info (Already Marked)

        if (type === "success") {
            iconClass = "fa-solid fa-circle-check text-success fa-lg"; // Green Tick (Match Found)
        } else if (type === "danger" || type === "error") {
            iconClass = "fa-solid fa-circle-xmark text-danger fa-lg";  // Red Cross (Mismatch/Error)
        } else if (type === "warning") {
            iconClass = "fa-solid fa-triangle-exclamation text-warning fa-lg"; // Yellow Triangle (Missing Input)
        }

        const variantClass = type === "success"
            ? "toast-success"
            : type === "danger" || type === "error"
                ? "toast-danger"
                : type === "warning"
                    ? "toast-warning"
                    : "toast-info";

        const toastEl = document.createElement("div");
        toastEl.className = `toast align-items-center border-0 mb-2 shadow ${variantClass}`;
        toastEl.setAttribute("role", "status");
        toastEl.setAttribute("aria-live", "polite");
        toastEl.setAttribute("aria-atomic", "true");
        toastEl.innerHTML = `
            <div class="d-flex p-1">
                <div class="toast-body d-flex align-items-center gap-2">
                    <i class="${iconClass} toast-icon me-1"></i>
                    <div class="d-flex flex-column lh-sm">
                        ${title ? '<strong class="toast-title">' + title + "</strong>" : ""}
                        <span class="small mt-1 toast-message">${message}</span>
                    </div>
                </div>
                <button type="button" class="btn-close toast-close-btn me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>`;

        container.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl, { autohide, delay });
        toast.show();

        // Ensure toasts sit above footer and above key action buttons without changing layout
        try {
            const footer = document.querySelector('footer');
            const footerHeight = footer ? (footer.offsetHeight || 0) : 0;

            let extra = 0;
            const actionBtn = document.querySelector('.btn-custom-primary');
            if (actionBtn) {
                const rect = actionBtn.getBoundingClientRect();
                const vwHeight = window.innerHeight || document.documentElement.clientHeight;
                const dist = Math.max(0, vwHeight - rect.bottom);
                const desiredGap = footerHeight + 12;
                if (dist < desiredGap) {
                    extra = desiredGap - dist;
                }
            }

            container.style.bottom = (footerHeight + 12 + extra) + 'px';
        } catch (e) {
            // ignore
        }

        // Remove toast HTML element when hidden to free up memory
        toastEl.addEventListener("hidden.bs.toast", function () {
            toastEl.remove();
        });
    };

    /**
     * ------------------------------------------------------------------------
     * 2. FILE UPLOAD UI HANDLER
     * ------------------------------------------------------------------------
     * Updates the text of the custom file upload button to show the selected filename.
     */
    window.handleFile = function (
        input,
        uploadTextId = "uploadText",
        options = {},
    ) {
        const uploadText = document.getElementById(uploadTextId);
        if (!uploadText) return;

        try {
            const file = input?.files?.[0] || null;
            if (file && file.name) {
                const icon = options.icon || "fa-solid fa-file-image me-2 text-success";
                uploadText.innerHTML = `<i class="${icon}"></i>Selected: ${file.name}`;
            } else if (!options.keepPlaceholder) {
                uploadText.innerHTML = `<i class="fa-solid fa-cloud-arrow-up me-2 text-primary"></i>Click to upload${options.label || " file"}`;
            }
        } catch (e) {
            console.error(e);
        }
    };

    /**
     * ------------------------------------------------------------------------
     * 3. MOCK FORM SUBMIT HANDLERS
     * ------------------------------------------------------------------------
     * Demonstrates Toast notifications during registration/login flows.
     */
    window.handleRegistrationSubmit = function (event) {
        event.preventDefault();
        showToast(
            "Registration successful! Redirecting to login...",
            "Registration",
            "success",
        );
        setTimeout(function () {
            window.location.href = "login.html";
        }, 1500);
    };

    window.handleLogin = function (event) {
        event.preventDefault();
        showToast(
            "Login successful! Redirecting to Live Terminal...",
            "Authentication",
            "success",
        );
        setTimeout(function () {
            window.location.href = "index.html";
        }, 1500);
    };

    /**
     * ------------------------------------------------------------------------
     * 4. RESPONSIVE NAVIGATION DRAWER
     * ------------------------------------------------------------------------
     * Initializes and toggles the mobile/tablet side navigation menu.
     */
    window.initMenuToggle = function (
        menuToggleId = "menuToggleBtn",
        navDrawerId = "navDrawer",
    ) {
        const toggleBtn = document.getElementById(menuToggleId);
        const navDrawer = document.getElementById(navDrawerId);
        if (!toggleBtn || !navDrawer) return;

        // Ensure hamburger buttons do not submit forms accidentally.
        if (toggleBtn.tagName === "BUTTON") {
            toggleBtn.type = "button";
        }

        toggleBtn.setAttribute("aria-controls", navDrawerId);
        toggleBtn.setAttribute("aria-expanded", "false");

        toggleBtn.addEventListener("click", function (event) {
            event.preventDefault();
            window.toggleMenu(menuToggleId, navDrawerId);
        });
    };

    window.toggleMenu = function (menuToggleId = "menuToggleBtn", navDrawerId = "navDrawer") {
        let toggleBtn;
        let navDrawer;

        if (menuToggleId && menuToggleId.target) {
            const evt = menuToggleId;
            toggleBtn = evt.currentTarget || (evt.target && evt.target.closest && evt.target.closest('button')) || evt.target;
            navDrawer = document.getElementById(navDrawerId || 'navDrawer');
        } else {
            toggleBtn = document.getElementById(menuToggleId);
            navDrawer = document.getElementById(navDrawerId);
        }

        if (!toggleBtn || !navDrawer) {
            console.debug('toggleMenu: missing elements', { toggleBtn, navDrawer });
            return;
        }

        const isExpanded = navDrawer.classList.toggle('show');
        try {
            toggleBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        } catch (e) {
            // ignore
        }
    };

    /**
     * ------------------------------------------------------------------------
     * 5. DYNAMIC DATE INITIALIZATION
     * ------------------------------------------------------------------------
     * Injects the current, localized date into a designated element on load.
     */
    window.initCurrentDate = function (dateElementId = "currentDate", options) {
        const dateEl = document.getElementById(dateElementId);
        if (!dateEl) return;
        const formatOptions = options || {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "numeric",
        };
        dateEl.textContent = new Date().toLocaleDateString(
            undefined,
            formatOptions,
        );
    };

    // Initialize UI components once the DOM is fully loaded
    document.addEventListener("DOMContentLoaded", function () {
        initMenuToggle();
        initCurrentDate();
    });
})();

/**
 * ------------------------------------------------------------------------
 * 6. PASSWORD VISIBILITY TOGGLE
 * ------------------------------------------------------------------------
 * Toggles the password input field between masked (dots) and text, swapping
 * the FontAwesome eye icon simultaneously.
 */
function togglePasswordVisibility(inputId, iconId) {
    const passwordInput = document.getElementById(inputId);
    const toggleIcon = document.getElementById(iconId);

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.classList.remove('fa-eye-slash');
        toggleIcon.classList.add('fa-eye'); // Shows open eye when text is visible
    } else {
        passwordInput.type = 'password';
        toggleIcon.classList.remove('fa-eye');
        toggleIcon.classList.add('fa-eye-slash'); // Shows closed eye when text is hidden
    }
}