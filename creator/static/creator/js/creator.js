// Extra Javascript handling and overrides for our creator page which loads the CardConjurer static creator page.

let ScryfallTimer = null;

const RARITIES = [
    ['', 'Select Rarity'],
    ['C', 'Common'],
    ['U', 'Uncommon'],
    ['R', 'Rare'],
    ['M', 'Mythic Rare'],
];

async function checkScryfall() {
    // Check if the selected text editor is mana cost and try to parse it from Scryfall.
    let selectedText = card.text[Object.keys(card.text)[selectedTextIndex]];
    if (selectedText.name.includes("Mana Cost")) {
        let result;
        try {
            result = await $.get(`https://api.scryfall.com/symbology/parse-mana?cost=${selectedText.text}`);
        }
        catch (error) {
            let msg = `Error parsing mana cost with Scryfall API: ${error.status}`;
            if (error.responseJSON) {
                msg += ` - ${error.responseJSON.details}`;
            }
            console.error(msg);
            return;
        }

        // Call text edited handler to update render.
        if (result.cost) {
            $("#text-editor").val(result.cost);
            textEdited();
        }
    }
}

function restartScryfallTimer() {
    clearTimeout(ScryfallTimer);
    ScryfallTimer = setTimeout(checkScryfall, 1000);
}

$(() => {
    // Remove fetch image from Gatherer option for now because it taints the canvas and you can't export.
    // There might be a way around this in the future but it doesn't work for now.
    $("#fetchSetSymbolFromGatherer").prop("checked", false).prop("disabled", true).parent().hide();
    $("#set-symbol-code").val(setSymbolCode);

    // Hide regular download buttons.
    $(".download").parent().hide();

    // Hide lock set symbol inputs.
    $("#creator-menu-setSymbol").children().slice(2).hide();

    // Hide auto load frame version checkbox (we'll do this programmatically in JS).
    $("#creator-menu-frame").children().eq(0).children().slice(3).hide();

    // Hook for editing mana cost text to parse with Scryfall API.
    $("#text-editor").on("input", restartScryfallTimer);

    // Replace set symbol rarity with a dropdown instead.
    // When we change the set symbol rarity, copy this to the bottom info rarity field for consistency by default.
    // Don't go the other way, because the bottom info code could be e.g. "P" for promo variant.
    let dropdown = $("<select>").attr("id", "set-symbol-rarity").addClass("input");
    for (let rarity of RARITIES) {
        $("<option>").attr("value", rarity[0]).text(rarity[1]).appendTo(dropdown);
    }
    dropdown.on("change", fetchSetSymbol).on("input", function() {
        $("#info-rarity").val($(this).val().toUpperCase());
        bottomInfoEdited();
    });
    $("#set-symbol-rarity").replaceWith(dropdown);

    // Remove other import/download tab options.
    let sections = $("#creator-menu-import").children();
    sections.slice(2, 4).hide();  // Download/delete section and how are my cards saved.

    // Save/load section.
    let saveload = sections.eq(1).children();
    saveload.slice(2).hide().prop("onclick", null).prop("onchange", null).off();

    // Remove existing save button click handler and add our own.
    let saveBtn = saveload.eq(1);
    saveBtn.prop("onclick", null).off("click");
    saveBtn.click(() => {
        // Make sure we have a name to save the card.
        let name = getCardName();
        if (!name || name === "unnamed") {
            notify('You must give your card a name to save it!', 5);
            return;
        }

        saveBtn.prop("disabled", true).text("Saving...");

        // Get generated preview image and call JSON API to save the card and the image.
        // Let's save the selected autoframe option for this card, if any.
        const cardToSave = JSON.parse(JSON.stringify(card));
        cardToSave.frames.forEach(frame => {
            delete frame.image;
            frame.masks.forEach(mask => delete mask.image);
        });
        cardToSave.autoFrame = $("#autoFrame").val();
        const imageDataURL = cardCanvas.toDataURL('image/png');

        let data = {
            pk: cardId,
            set: setId,
        }

        if (EDITING_BACK) {
            data.back = cardToSave;
            data.back_image = imageDataURL;
        }
        else {
            data.front = cardToSave;
            data.front_image = imageDataURL;
        }

        const settings = {
            data: JSON.stringify(data),
            contentType: "application/json; charset=utf-8",
            dataType: "json",
            headers: {
                // CSRF token must be passed via headers for AJAX calls.
                "X-CSRFToken": Cookies.get('csrftoken')
            },
            url: SAVE_URL
        };
        $.post(settings).done((data) => {
            // Redirect to card viewing page.
            saveBtn.text("Saved!");
            location.href = data.view_url;
        }).fail(() => {
            saveBtn.prop("disabled", false).text("Save Card");
            notify('There was an error saving your card.', 5);
        });
    });

    // Get card data if we're editing an existing card and load it using the CardConjurer function.
    // We have to temporarily store this in the local storage because this is how CardConjurer works internally.
    let data = $("#card-data").text();
    if (data) {
        // If we have rules text, run it through the updated curly quotes function when we load.
        data = JSON.parse(data);
        if (data.text && data.text.rules && data.text.rules.text) {
            data.text.rules.text = curlyQuotes(data.text.rules.text);
        }

        localStorage.setItem("editData", JSON.stringify(data));
        loadCard("editData").then(() => {
            // Sometimes font doesn't load right away and first text render fails.  This is a hack workaround...
            setTimeout(textEdited, 2000);
            setTimeout(bottomInfoEdited, 2000);
            setTimeout(resetSetSymbol, 2000);
        });
    }

    // Turn auto load frame version back on if the frame group or autoframe selection changes at all.
    $("#selectFrameGroup, #autoFrame").on("change", () => {
        $("#autoLoadFrameVersion").prop("checked", true);
        localStorage.setItem('autoLoadFrameVersion', true);
    });
});
