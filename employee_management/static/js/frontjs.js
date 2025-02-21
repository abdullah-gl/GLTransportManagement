// Function to load pages dynamically
function loadPage(page) {
    const mainContent = document.getElementById('main-content');
    const sidebarLinks = document.querySelectorAll('.sidebar-links li a');
    
    // Reset the styles for sidebar links
    sidebarLinks.forEach(link => link.classList.remove('active'));
    
    // Add active class to the clicked link
    event.target.classList.add('active');
    
    if (page === 'employee') {
      document.title = "Employee | Transport GTPL";
      mainContent.innerHTML = `
        <h2>Employee</h2>
        <p>Employee-specific content goes here.</p>
      `;
      window.history.pushState({}, '', '/employee');
    } else if (page === 'vendor') {
      document.title = "Vendor | Transport GTPL";
      mainContent.innerHTML = `
        <h2>Vendor</h2>
        <p>Vendor-specific content goes here.</p>
      `;
      window.history.pushState({}, '', '/vendor');
    } else if (page === 'profile') {
      mainContent.innerHTML = `
        <h2>Profile</h2>
        <br>
        <p>Your profile information goes here.</p>
      `;
    } else if (page === 'settings') {
      mainContent.innerHTML = `
        <h2>Settings</h2>
        <p>Settings management page.</p>
      `;
    }
  }
  
  // Event listener for the back and forward buttons
  window.onpopstate = function() {
    const path = window.location.pathname;
    if (path === '/employee') {
      loadPage('employee');
    } else if (path === '/vendor') {
      loadPage('vendor');
    }
  };
  

// Load Employee page by default when site opens
window.onload = function() {
    loadPage('employee.html');
};


document.addEventListener("DOMContentLoaded", function () {
  const sidebar = document.querySelector(".sidebar");
  const toggleButton = document.getElementById("sidebar-toggle");

  toggleButton.addEventListener("click", function () {
    sidebar.classList.toggle("open");
    toggleButton.classList.toggle("move");
  });
});
  
  