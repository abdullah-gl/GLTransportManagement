document.addEventListener("DOMContentLoaded", function () {
    var actionButtons = document.getElementById("actionButtons");
    var confirmButton = document.getElementById("confirmButton");
    var cancelPopup = document.getElementById("cancelPopup");

    // Ensure buttons are hidden initially
    if (actionButtons) {
        actionButtons.style.display = "none";
    }

    // Show buttons when the Confirm button is clicked
    if (confirmButton) {
        confirmButton.addEventListener("click", function () {
            if (actionButtons) {
                actionButtons.style.display = "flex";
            }
            document.getElementById("confirmModal").classList.remove("show"); // Hide modal after confirmation
            document.body.classList.remove("modal-open"); // Remove modal backdrop effect
        });
    }

    // Hide buttons again if Cancel is clicked
    if (cancelPopup) {
        cancelPopup.addEventListener("click", function () {
            if (actionButtons) {
                actionButtons.style.display = "none";
            }
        });
    }
});