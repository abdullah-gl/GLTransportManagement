// Initialize tooltips
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Form validation
(function () {
    'use strict';
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
})();


document.getElementById('tableSearch').addEventListener('input', function (e) {
    const searchText = e.target.value.toLowerCase();
    const table = document.getElementById('dataTable');
    const rows = table.getElementsByTagName('tr');
    let noMatchesFound = true;

    // Skip header row (index 0)
    for (let i = 1; i < rows.length; i++) {
        const row = rows[i];
        const cells = row.getElementsByTagName('td');
        let rowText = '';
        let found = false;

        // Combine all cell text in the row
        for (let cell of cells) {
            rowText += cell.textContent.toLowerCase() + ' ';
        }

        // Check if search text exists in row text
        if (rowText.includes(searchText)) {
            row.style.display = '';
            found = true;
            noMatchesFound = false;

            // Highlight matching text if search box is not empty
            if (searchText.length > 0) {
                for (let cell of cells) {
                    const cellText = cell.textContent;
                    if (cellText.toLowerCase().includes(searchText)) {
                        cell.classList.add('highlight');
                    } else {
                        cell.classList.remove('highlight');
                    }
                }
            } else {
                // Remove highlights if search box is empty
                for (let cell of cells) {
                    cell.classList.remove('highlight');
                }
            }
        } else {
            row.style.display = 'none';
        }
    }

    // Show no results message if no matches found
    const existingMessage = document.getElementById('noResultsMessage');
    if (noMatchesFound && searchText.length > 0) {
        if (!existingMessage) {
            const message = document.createElement('div');
            message.id = 'noResultsMessage';
            message.className = 'alert alert-info mt-3';
            message.innerHTML = '<i class="bi bi-info-circle me-2"></i>No matching records found';
            table.parentNode.appendChild(message);
        }
    } else if (existingMessage) {
        existingMessage.remove();
    }
});

// Debounce function to improve search performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Apply debouncing to search
const searchInput = document.getElementById('tableSearch');
const debouncedSearch = debounce((e) => {
    const event = new Event('input');
    searchInput.dispatchEvent(event);
}, 300);

searchInput.addEventListener('input', debouncedSearch);









document.addEventListener("DOMContentLoaded", function () {
    // Attach event listener to the send email button
    document.getElementById("confirmSendEmail")?.addEventListener("click", handleSendEmail);
});

function handleSendEmail() {
    let sendButton = document.getElementById("confirmSendEmail");
    let loader = document.getElementById("emailLoader");
    let modalBody = document.getElementById("modalBody");
    
    if (!sendButton || !loader || !modalBody) {
        console.error("Missing modal elements");
        return;
    }

    // Show loading indicator and disable button
    showLoader(modalBody, loader, sendButton);
    
    // Send email request and handle response
    sendEmailRequest()
        .then(() => handleSuccess(modalBody, loader))
        .catch(error => handleError(modalBody, loader, error))
        .finally(() => sendButton.disabled = false);
}

function showLoader(modalBody, loader, sendButton) {
    // Clear modal content and show loading animation
    modalBody.innerHTML = '';
    modalBody.appendChild(loader);
    loader.classList.remove("d-none");
    sendButton.disabled = true;
    console.log("Send Email button clicked");
}

function sendEmailRequest() {
    // Send POST request to server with CSRF token
    return fetch(sendEmployeeEmailsUrl, {
        method: "POST",
        headers: {
            "X-CSRFToken": csrfToken,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({})
    }).then(response => {
        if (!response.ok) {
            throw new Error("Network response was not ok");
        }
        return response.json();
    });
}

function handleSuccess(modalBody, loader) {
    // Handle successful email send
    console.log("Email sent successfully");
    loader.classList.add("d-none");
    modalBody.innerHTML = '<p class="text-success">Email sent successfully!</p>';
    setTimeout(closeModal, 1500);
}

function handleError(modalBody, loader, error) {
    // Handle email send failure
    console.error("Error sending email:", error);
    alert("An error occurred while sending the email. Please check the console for details.");
    loader.classList.add("d-none");
    modalBody.innerHTML = '<p class="text-danger">Failed to send email. Please try again.</p>';
}

function closeModal() {
    // Close the modal and remove backdrop
    let modalElement = document.getElementById("confirmModal");
    if (!modalElement) return;
    
    let modalInstance = bootstrap.Modal.getInstance(modalElement) || new bootstrap.Modal(modalElement);
    modalInstance.hide();
    document.body.classList.remove("modal-open");
    document.querySelector(".modal-backdrop")?.remove();
}










// document.addEventListener('DOMContentLoaded', function () {
//     // Check the URL hash or any condition to determine the active tab
//     const hash = window.location.hash;

//     if (hash === '#employee-section') {
//         // Activate the Employee tab
//         const employeeTab = new bootstrap.Tab(document.getElementById('employee-tab'));
//         employeeTab.show();
//     } else if (hash === '#vendor-section') {
//         // Activate the Vendor tab
//         const vendorTab = new bootstrap.Tab(document.getElementById('vendor-tab'));
//         vendorTab.show();
//     } else {
//         // Default to Employee tab if no hash is present
//         const defaultTab = new bootstrap.Tab(document.getElementById('employee-tab'));
//         defaultTab.show();
//     }
// });
