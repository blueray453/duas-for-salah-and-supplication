document.addEventListener("DOMContentLoaded", function () {
    // Select the TOC container
    let tocDiv = document.querySelector(".toc");
    // Select all h2 and h3 elements for ToC generation
    let headings = document.querySelectorAll("h2, h3");

    headings.forEach((heading, index) => {
        let id = heading.id || `section${index + 1}`;
        heading.id = id; // Ensure ID exists

        let tocEntry = document.createElement("p");
        let tocLink = document.createElement("a");

        tocLink.href = `#${id}`;
        tocLink.textContent = heading.textContent;

        tocEntry.appendChild(tocLink);

        // If it's a <h3>, indent it in the ToC
        if (heading.tagName === "H3") {
            tocEntry.classList.add("sub");
        }

        tocDiv.appendChild(tocEntry);
    });
});