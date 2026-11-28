(() => {
    const inlinePattern =
        /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))|(`([^`]+)`)|(\*\*([^*]+)\*\*)|(__([^_]+)__)|(\*([^*]+)\*)|(_([^_]+)_)/g;
    const listPattern = /^\s*([-*+])\s+(.+)|^\s*(\d+)\.\s+(.+)/;
    const headingPattern = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/;

    function appendInline(parent, text) {
        let lastIndex = 0;

        for (const match of text.matchAll(inlinePattern)) {
            parent.append(document.createTextNode(text.slice(lastIndex, match.index)));

            if (match[2]) {
                try {
                    const url = new URL(match[3]);
                    if (url.protocol === "http:" || url.protocol === "https:") {
                        const link = document.createElement("a");
                        link.className = "font-medium text-cyan-800 underline underline-offset-2";
                        link.href = url.href;
                        link.rel = "noopener noreferrer";
                        link.target = "_blank";
                        link.textContent = match[2];
                        parent.append(link);
                    } else {
                        parent.append(document.createTextNode(match[0]));
                    }
                } catch {
                    parent.append(document.createTextNode(match[0]));
                }
            } else if (match[5]) {
                const code = document.createElement("code");
                code.className = "rounded bg-slate-200 px-1.5 py-0.5 font-mono text-[0.9em]";
                code.textContent = match[5];
                parent.append(code);
            } else if (match[7] || match[9]) {
                const strong = document.createElement("strong");
                strong.textContent = match[7] || match[9];
                parent.append(strong);
            } else {
                const emphasis = document.createElement("em");
                emphasis.textContent = match[11] || match[13];
                parent.append(emphasis);
            }

            lastIndex = match.index + match[0].length;
        }

        parent.append(document.createTextNode(text.slice(lastIndex)));
    }

    function isBlockStart(line) {
        return headingPattern.test(line)
            || /^\s*```/.test(line)
            || /^\s*>/.test(line)
            || /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)
            || listPattern.test(line);
    }

    function renderMarkdown(markdown) {
        const fragment = document.createDocumentFragment();
        const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
        let index = 0;

        while (index < lines.length) {
            const line = lines[index];
            if (!line.trim()) {
                index += 1;
                continue;
            }

            if (/^\s*```/.test(line)) {
                index += 1;
                const codeLines = [];
                while (index < lines.length && !/^\s*```/.test(lines[index])) {
                    codeLines.push(lines[index]);
                    index += 1;
                }
                if (index < lines.length) index += 1;

                const pre = document.createElement("pre");
                pre.className = "mt-4 overflow-x-auto rounded-xl bg-slate-950 p-4 text-sm text-slate-100";
                const code = document.createElement("code");
                code.className = "font-mono";
                code.textContent = codeLines.join("\n");
                pre.append(code);
                fragment.append(pre);
                continue;
            }

            const heading = line.match(headingPattern);
            if (heading) {
                const level = heading[1].length;
                const element = document.createElement(`h${level}`);
                element.className = level === 1
                    ? "mt-5 text-2xl font-bold tracking-tight text-slate-950 first:mt-0"
                    : level === 2
                        ? "mt-5 text-xl font-bold text-slate-950"
                        : "mt-4 text-lg font-bold text-slate-900";
                appendInline(element, heading[2]);
                fragment.append(element);
                index += 1;
                continue;
            }

            if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
                const rule = document.createElement("hr");
                rule.className = "my-4 border-slate-200";
                fragment.append(rule);
                index += 1;
                continue;
            }

            if (/^\s*>/.test(line)) {
                const quote = document.createElement("blockquote");
                quote.className = "mt-4 border-l-4 border-slate-300 pl-4 italic text-slate-600";
                const paragraph = document.createElement("p");
                while (index < lines.length && /^\s*>/.test(lines[index])) {
                    const content = lines[index].replace(/^\s*>\s?/, "");
                    if (paragraph.childNodes.length) paragraph.append(document.createElement("br"));
                    appendInline(paragraph, content);
                    index += 1;
                }
                quote.append(paragraph);
                fragment.append(quote);
                continue;
            }

            const listMatch = line.match(listPattern);
            if (listMatch) {
                const ordered = listMatch[3] !== undefined;
                const list = document.createElement(ordered ? "ol" : "ul");
                list.className = ordered
                    ? "mt-3 list-decimal space-y-1 pl-6 marker:text-cyan-700"
                    : "mt-3 list-disc space-y-1 pl-6 marker:text-cyan-700";

                while (index < lines.length) {
                    const itemMatch = lines[index].match(listPattern);
                    if (!itemMatch || (itemMatch[3] !== undefined) !== ordered) break;
                    const item = document.createElement("li");
                    item.className = "pl-1";
                    appendInline(item, ordered ? itemMatch[4] : itemMatch[2]);
                    list.append(item);
                    index += 1;
                }
                fragment.append(list);
                continue;
            }

            const paragraphLines = [line.trim()];
            index += 1;
            while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
                paragraphLines.push(lines[index].trim());
                index += 1;
            }

            const paragraph = document.createElement("p");
            paragraph.className = "mt-3 first:mt-0";
            appendInline(paragraph, paragraphLines.join(" "));
            fragment.append(paragraph);
        }

        return fragment;
    }

    document.querySelectorAll("[data-markdown-viewer]").forEach((viewer) => {
        viewer.replaceChildren(renderMarkdown(viewer.textContent));
    });
})();
