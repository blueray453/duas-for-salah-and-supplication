
document.addEventListener("DOMContentLoaded", function () {
    const mappings = {
        AAM: "Al-Adab Al-Mufrad",
        BM: "Bulugh al-Maram",
        HM: "Hisn al-Muslim",
        JT: "Jami` at-Tirmidhi",
        MA: "Musnad Ahmad",
        MAM: "Mishkat al-Masabih",
        N: "Nafl Prayer",
        RAS: "Riyad as-Salihin",
        SAB: "Sahih al-Bukhari",
        SAN: "Sunan an-Nasa'i",
        SD: "Sunan Abi Dawud",
        SIM: "Sunan Ibn Majah",
        SM: "Sahih Muslim",
        T: "Tahajjud"
    };

    document.querySelectorAll('.paragraph.reference p').forEach(p => {
        p.innerHTML = p.innerHTML
            // Replace abbreviations like SAN, SAB, etc.
            .replace(/\b(AAM|SAN|MA|MAM|HM|JT|BM|SAB|SM|SD|SIM|RAS)\b/g, match => {
                return `<span class="ref ${match}" title="${mappings[match]}">${mappings[match]}</span>`;
            })
            // Replace (T) and (N) with their long forms
            .replace(/\((T|N)\)/g, (match, p1) => {
                return `<span class="ref ${p1}" title="${mappings[p1]}">(${mappings[p1]})</span>`;
            });
    });
});
