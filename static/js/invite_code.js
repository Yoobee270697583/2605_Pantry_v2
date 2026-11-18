// the invite code box on My Kitchen and the Household page.
// Copy copies the code that's showing, and New code swaps in a new one without reloading the page.
// without JavaScript, New code is still a normal form that reloads the page.
document.querySelectorAll("[data-copy-invite]").forEach((button) => {
    button.addEventListener("click", () => {
        const code = button.closest("div").querySelector("[data-invite-code]").textContent.trim();
        navigator.clipboard.writeText(code);
        button.textContent = "Copied";
        setTimeout(() => { button.textContent = "Copy"; }, 2000);
    });
});

document.querySelectorAll("[data-new-code]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button");
        const box = form.closest(".card-body");
        if (button.disabled) return;   // already working
        button.disabled = true;

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),   // includes the CSRF token from {% csrf_token %}
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            box.querySelector("[data-invite-code]").textContent = data.code;
            box.querySelector("[data-invite-until]").textContent = data.works_until;
            button.textContent = "New code made";
            setTimeout(() => { button.textContent = "New code"; }, 2000);
        } catch (error) {
            form.submit();   // something went wrong - fall back to the normal form
            return;
        } finally {
            button.disabled = false;
        }
    });
});
