
(() => {
    const DEFAULT_LANGUAGE = "zh-CN";
    const SUPPORTED_LANGUAGES = ["zh-CN", "en-CA"];
    const STORAGE_KEY = "lan-doudizhu-language";

    let currentLanguage = DEFAULT_LANGUAGE;
    let translations = {};

    const localeCache = new Map();

    async function fetchLocale(language) {
        if (localeCache.has(language)) {
            return localeCache.get(language);
        }

        const response = await fetch(`locales/${language}.json`);

        if (!response.ok) {
            throw new Error(`Failed to load locale: ${language}`);
        }

        const locale = await response.json();
        localeCache.set(language, locale);

        return locale;
    }

    function getSavedLanguage() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (error) {
            console.warn(
                "[i18n] Language preference storage is unavailable:",
                error
            );
            return null;
        }
    }

    function saveLanguage(language) {
        try {
            localStorage.setItem(STORAGE_KEY, language);
        } catch (error) {
            console.warn(
                "[i18n] Could not save language preference:",
                error
            );
        }
    }

    function translate(key, values = {}) {
        let result = translations[key] ?? key;

        for (const [name, value] of Object.entries(values)) {
            result = result.replaceAll(`{${name}}`, String(value));
        }

        return result;
    }

    function updateLanguagePicker() {
        const current = document.getElementById("language-current");
        const menu = document.getElementById("language-menu");
        const trigger = document.getElementById("language-trigger");

        if (current) {
            current.textContent = translations.language || currentLanguage;
        }

        if (menu) {
            menu.querySelectorAll("[data-language]").forEach(option => {
                const active =
                    option.dataset.language === currentLanguage;

                option.classList.toggle("active", active);
                option.setAttribute("aria-checked", String(active));
            });
        }

        if (trigger) {
            trigger.setAttribute(
                "aria-expanded",
                String(Boolean(menu && !menu.classList.contains("hidden")))
            );
        }
    }

    function applyTranslations(root = document) {
        root.querySelectorAll("[data-i18n]").forEach(element => {
            element.textContent = translate(element.dataset.i18n);
        });

        root.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
            element.placeholder = translate(
                element.dataset.i18nPlaceholder
            );
        });

        root.querySelectorAll("[data-i18n-title]").forEach(element => {
            element.title = translate(element.dataset.i18nTitle);
        });

        const title = document.querySelector(
            "[data-i18n-document-title]"
        );

        if (title) {
            document.title = translate(title.dataset.i18nDocumentTitle);
        }

        updateLanguagePicker();
    }

    async function loadLanguage(language) {
        if (!SUPPORTED_LANGUAGES.includes(language)) {
            return false;
        }

        try {
            const locale = await fetchLocale(language);

            translations = locale;
            currentLanguage = language;

            document.documentElement.lang = language;

            saveLanguage(language);
            applyTranslations();

            window.dispatchEvent(
                new CustomEvent("languagechange", {
                    detail: { language }
                })
            );

            return true;
        } catch (error) {
            console.error("[i18n] Language loading failed:", error);
            return false;
        }
    }

    function closeLanguageMenu(returnFocus = false) {
        const menu = document.getElementById("language-menu");
        const trigger = document.getElementById("language-trigger");

        if (!menu || !trigger) {
            return;
        }

        menu.classList.add("hidden");
        trigger.setAttribute("aria-expanded", "false");

        if (returnFocus) {
            trigger.focus();
        }
    }

    function initializeLanguagePicker(availableLocales) {
        const picker = document.getElementById("language-picker");
        const trigger = document.getElementById("language-trigger");
        const menu = document.getElementById("language-menu");

        if (!picker || !trigger || !menu) {
            console.warn(
                "[i18n] Custom language picker markup was not found."
            );
            return;
        }

        menu.replaceChildren();

        for (const { language, locale } of availableLocales) {
            const option = document.createElement("button");

            option.type = "button";
            option.className = "language-option";
            option.dataset.language = language;
            option.setAttribute("role", "menuitemradio");
            option.setAttribute("aria-checked", "false");
            option.textContent = locale.language || language;

            option.addEventListener("click", async () => {
                const success = await loadLanguage(language);

                if (success) {
                    closeLanguageMenu();
                }
            });

            menu.appendChild(option);
        }

        trigger.addEventListener("click", () => {
            const willOpen = menu.classList.contains("hidden");

            menu.classList.toggle("hidden", !willOpen);
            trigger.setAttribute("aria-expanded", String(willOpen));

            if (willOpen) {
                const selected = menu.querySelector(
                    `[data-language="${currentLanguage}"]`
                );

                (selected || menu.querySelector("button"))?.focus();
            }
        });

        picker.addEventListener("keydown", event => {
            if (
                event.key === "Escape" &&
                !menu.classList.contains("hidden")
            ) {
                event.preventDefault();
                closeLanguageMenu(true);
            }
        });

        document.addEventListener("click", event => {
            if (!picker.contains(event.target)) {
                closeLanguageMenu();
            }
        });

        menu.addEventListener("keydown", event => {
            const options = [...menu.querySelectorAll("button")];
            const index = options.indexOf(document.activeElement);

            let nextIndex = index;

            if (event.key === "ArrowDown") {
                nextIndex = (index + 1) % options.length;
            } else if (event.key === "ArrowUp") {
                nextIndex =
                    (index - 1 + options.length) % options.length;
            } else if (event.key === "Home") {
                nextIndex = 0;
            } else if (event.key === "End") {
                nextIndex = options.length - 1;
            } else {
                return;
            }

            event.preventDefault();
            options[nextIndex]?.focus();
        });
    }

    async function initialize() {
        const results = await Promise.all(
            SUPPORTED_LANGUAGES.map(async language => {
                try {
                    return {
                        language,
                        locale: await fetchLocale(language)
                    };
                } catch (error) {
                    console.error(
                        `[i18n] Cannot load ${language}:`,
                        error
                    );
                    return null;
                }
            })
        );

        const availableLocales = results.filter(Boolean);

        if (availableLocales.length === 0) {
            console.error("[i18n] No language files available.");
            return false;
        }

        initializeLanguagePicker(availableLocales);

        const savedLanguage = getSavedLanguage();
        const browserLanguage =
            (navigator.language || "").toLowerCase();

        const preferredLanguage =
            savedLanguage ||
            (browserLanguage.startsWith("en")
                ? "en-CA"
                : DEFAULT_LANGUAGE);

        const availableCodes = availableLocales.map(
            item => item.language
        );

        const initialLanguage = availableCodes.includes(preferredLanguage)
            ? preferredLanguage
            : availableCodes.includes(DEFAULT_LANGUAGE)
                ? DEFAULT_LANGUAGE
                : availableCodes[0];

        return loadLanguage(initialLanguage);
    }

    window.i18n = {
        t: translate,
        setLanguage: loadLanguage,
        applyTranslations,

        get language() {
            return currentLanguage;
        },

        get supportedLanguages() {
            return [...SUPPORTED_LANGUAGES];
        }
    };

    window.i18nReady = initialize();
})();
