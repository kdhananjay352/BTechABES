(function () {
    "use strict";

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

    window.showToast = function (
        message,
        title = "",
        type = "info",
        autohide = true,
        delay = 4000,
    ) {
        const container = createToastContainer();
        if (!container) return;

        const iconClass =
            type === "success"
                ? "fa-solid fa-circle-check text-success fa-lg"
                : type === "error"
                    ? "fa-solid fa-circle-xmark text-danger fa-lg"
                    : "fa-solid fa-circle-info text-primary fa-lg";

        const toastEl = document.createElement("div");
        toastEl.className = "toast align-items-center text-bg-light border-0 mb-2";
        toastEl.setAttribute("role", "status");
        toastEl.setAttribute("aria-live", "polite");
        toastEl.setAttribute("aria-atomic", "true");
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center gap-2">
                    <i class="${iconClass}"></i>
                    <div>
                        ${title ? '<strong class="me-2">' + title + "</strong>" : ""}
                        <span>${message}</span>
                    </div>
                </div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>`;

        container.appendChild(toastEl);
        const toast = new bootstrap.Toast(toastEl, { autohide, delay });
        toast.show();

        // Ensure toasts sit above footer and above key action buttons without changing layout
        try {
            const footer = document.querySelector('footer');
            const footerHeight = footer ? (footer.offsetHeight || 0) : 0;

            // If there is a prominent action button near the viewport bottom (e.g. capture button),
            // make sure toasts appear above it instead of overlapping it.
            let extra = 0;
            const actionBtn = document.querySelector('.btn-custom-primary');
            if (actionBtn) {
                const rect = actionBtn.getBoundingClientRect();
                const vwHeight = window.innerHeight || document.documentElement.clientHeight;
                // distance from button bottom to viewport bottom
                const dist = Math.max(0, vwHeight - rect.bottom);
                // if the button is close to bottom (less than footerHeight + 12), add extra offset
                const desiredGap = footerHeight + 12;
                if (dist < desiredGap) {
                    extra = desiredGap - dist;
                }
            }

            container.style.bottom = (footerHeight + 12 + extra) + 'px';
        } catch (e) {
            // ignore
        }

        // remove toast element when hidden
        toastEl.addEventListener("hidden.bs.toast", function () {
            toastEl.remove();
        });
    };

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

        // Called with an Event object (inline onclick passes event)
        if (menuToggleId && menuToggleId.target) {
            const evt = menuToggleId;
            toggleBtn = evt.currentTarget || (evt.target && evt.target.closest && evt.target.closest('button')) || evt.target;
            navDrawer = document.getElementById(navDrawerId || 'navDrawer');
        } else {
            // Called with IDs (init binding)
            toggleBtn = document.getElementById(menuToggleId);
            navDrawer = document.getElementById(navDrawerId);
        }

        if (!toggleBtn || !navDrawer) {
            console.debug('toggleMenu: missing elements', { toggleBtn, navDrawer });
            return;
        }

        console.debug('toggleMenu: toggling', toggleBtn, navDrawer);
        const isExpanded = navDrawer.classList.toggle('show');
        try {
            toggleBtn.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        } catch (e) {
            // ignore
        }
    };

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

    document.addEventListener("DOMContentLoaded", function () {
        initMenuToggle();
        initCurrentDate();
    });
})();
