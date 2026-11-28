document.querySelectorAll("[data-analysis-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector('button[type="submit"]');
        const status = form.querySelector("[data-analysis-status]");
        if (!button) return;

        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.textContent = "Analyzing...";
        status?.classList.remove("hidden");
    });
});
