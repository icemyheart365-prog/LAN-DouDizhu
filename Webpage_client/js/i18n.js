(() => {
    const DEFAULT_LANGUAGE = "zh-CN";
    const SUPPORTED_LANGUAGES = ["zh-CN", "en-CA"];

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

    async function loadLanguage(language) {
        if (!SUPPORTED_LANGUAGES.includes(language)) {
            return false;
        }

        try {
            const locale = await fetchLocale(language);

            translations = locale;
            currentLanguage = language;

            document.documentElement.lang = language;
            localStorage.setItem("lan-doudizhu-language", language);

            applyTranslations();

            const selector = document.getElementById("language-select");
            if (selector) {
                selector.value = language;
            }

            return true;
        } catch (error) {
            console.error("[i18n] Language loading failed:", error);
            return false;
        }
    }

    function translate(key, values = {}) {
        let result = translations[key] ?? key;

        for (const [name, value] of Object.entries(values)) {
            result = result.replaceAll(`{${name}}`, String(value));
        }

        return result;
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

        const title = document.querySelector("[data-i18n-document-title]");

        if (title) {
            document.title = translate(title.dataset.i18nDocumentTitle);
        }
    }

    async function initialize() {
        const selector = document.getElementById("language-select");

        // Load language metadata from the existing locale JSON files.
        const results = await Promise.all(
            SUPPORTED_LANGUAGES.map(async language => {
                try {
                    const locale = await fetchLocale(language);
                    return { language, locale };
                } catch (error) {
                    console.error(`[i18n] Cannot load ${language}:`, error);
                    return null;
                }
            })
        );

        const availableLocales = results.filter(Boolean);

        if (selector) {
            selector.innerHTML = "";

            availableLocales.forEach(({ language, locale }) => {
                const option = document.createElement("option");
                option.value = language;
                option.textContent = locale.language || language;
                selector.appendChild(option);
            });

            selector.addEventListener("change", async () => {
                const success = await loadLanguage(selector.value);

                if (!success) {
                    selector.value = currentLanguage;
                }
            });
        }

        const savedLanguage = localStorage.getItem(
            "lan-doudizhu-language"
        );

        const browserLanguage = navigator.language.toLowerCase();

        const preferredLanguage =
            savedLanguage ||
            (browserLanguage.startsWith("en") ? "en-CA" : DEFAULT_LANGUAGE);

        const availableCodes = availableLocales.map(item => item.language);

        const initialLanguage = availableCodes.includes(preferredLanguage)
            ? preferredLanguage
            : availableCodes.includes(DEFAULT_LANGUAGE)
                ? DEFAULT_LANGUAGE
                : availableCodes[0];

        if (!initialLanguage) {
            console.error("[i18n] No language files available.");
            return false;
        }

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
