/* ÇELMAK Stok Takip - JavaScript */

// Document Ready
document.addEventListener('DOMContentLoaded', function () {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function () {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function (alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Mobile sidebar toggle
    var sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            document.querySelector('.sidebar').classList.toggle('show');
        });
    }
});

// Format number with thousand separator
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

// Confirm delete
function confirmDelete(message) {
    return confirm(message || 'Bu işlemi silmek istediğinizden emin misiniz?');
}

// Show loading spinner
function showLoading(element) {
    element.innerHTML = '<span class="loading-spinner"></span> Yükleniyor...';
    element.disabled = true;
}

// Hide loading spinner
function hideLoading(element, originalText) {
    element.innerHTML = originalText;
    element.disabled = false;
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function () {
        showToast('Kopyalandı!', 'success');
    });
}

// Show toast notification
function showToast(message, type) {
    var toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }

    var toastId = 'toast-' + Date.now();
    var bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-primary';

    var toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    var toastElement = document.getElementById(toastId);
    var toast = new bootstrap.Toast(toastElement);
    toast.show();
}

// Print element
function printElement(elementId) {
    var element = document.getElementById(elementId);
    if (!element) return;

    var printWindow = window.open('', '_blank');
    printWindow.document.write('<html><head><title>Yazdır</title>');
    printWindow.document.write('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">');
    printWindow.document.write('</head><body class="p-4">');
    printWindow.document.write(element.innerHTML);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    printWindow.print();
}

// Search filter for tables
function filterTable(inputId, tableId) {
    var input = document.getElementById(inputId);
    var filter = input.value.toLowerCase();
    var table = document.getElementById(tableId);
    var rows = table.getElementsByTagName('tr');

    for (var i = 1; i < rows.length; i++) {
        var cells = rows[i].getElementsByTagName('td');
        var found = false;

        for (var j = 0; j < cells.length; j++) {
            if (cells[j].textContent.toLowerCase().indexOf(filter) > -1) {
                found = true;
                break;
            }
        }

        rows[i].style.display = found ? '' : 'none';
    }
}

// Auto-complete search
function initAutoComplete(inputId, url, onSelect) {
    var input = document.getElementById(inputId);
    if (!input) return;

    var timeout = null;

    input.addEventListener('input', function () {
        clearTimeout(timeout);
        var query = this.value;

        if (query.length < 2) return;

        timeout = setTimeout(function () {
            fetch(url + '?q=' + encodeURIComponent(query))
                .then(response => response.json())
                .then(data => {
                    // Show dropdown with results
                    var dropdown = document.getElementById(inputId + '-dropdown');
                    if (!dropdown) {
                        dropdown = document.createElement('div');
                        dropdown.id = inputId + '-dropdown';
                        dropdown.className = 'dropdown-menu show';
                        input.parentNode.appendChild(dropdown);
                    }

                    dropdown.innerHTML = '';
                    data.forEach(function (item) {
                        var option = document.createElement('a');
                        option.className = 'dropdown-item';
                        option.href = '#';
                        option.textContent = item.name;
                        option.addEventListener('click', function (e) {
                            e.preventDefault();
                            onSelect(item);
                            dropdown.classList.remove('show');
                        });
                        dropdown.appendChild(option);
                    });
                });
        }, 300);
    });
}

// Number input validation (positive only)
document.querySelectorAll('input[type="number"]').forEach(function (input) {
    input.addEventListener('input', function () {
        if (this.value < 0) this.value = 0;
    });
});

// Form validation feedback
document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
        if (!form.checkValidity()) {
            e.preventDefault();
            e.stopPropagation();
        }
        form.classList.add('was-validated');
    });
});
