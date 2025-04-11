document.addEventListener('DOMContentLoaded', function() {
    const downloadForm = document.getElementById('download-form');
    const pinterestUrlInput = document.getElementById('pinterest-url');
    const downloadBtn = document.getElementById('download-btn');
    const loader = document.getElementById('loader');
    const result = document.getElementById('result');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    const videoSize = document.getElementById('video-size');
    const videoType = document.getElementById('video-type');
    const videoTitle = document.getElementById('video-title');
    const videoThumbnail = document.getElementById('video-thumbnail');
    const downloadLink = document.getElementById('download-link');
    const newSearchBtn = document.getElementById('new-search');
    const tryAgainBtn = document.getElementById('try-again');

    // Form submission
    downloadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const url = pinterestUrlInput.value.trim();
        
        if (!url) {
            showError('Please enter a Pinterest video URL');
            return;
        }
        
        if (!isValidPinterestUrl(url)) {
            showError('Please enter a valid Pinterest video URL');
            return;
        }
        
        // Show loader and hide other sections
        showLoader();
        
        // Send request to server
        const formData = new FormData();
        formData.append('url', url);
        
        fetch('/download', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            hideLoader();
            
            if (data.success) {
                showResult(data);
            } else {
                showError(data.error || 'Failed to download video');
            }
        })
        .catch(error => {
            hideLoader();
            showError('An error occurred. Please try again.');
            console.error('Error:', error);
        });
    });
    
    // New search button
    newSearchBtn.addEventListener('click', function() {
        resetForm();
    });
    
    // Try again button
    tryAgainBtn.addEventListener('click', function() {
        resetForm();
    });
    
    // Helper functions
    function isValidPinterestUrl(url) {
        // More flexible pattern to accept various Pinterest URL formats
        const pattern = /^https?:\/\/(www\.)?(pinterest\.(com|ca|co\.uk|fr|de|ch|jp|au|in)|pin\.it).*/;
        return pattern.test(url);
    }
    
    function showLoader() {
        downloadForm.classList.add('hidden');
        result.classList.add('hidden');
        errorMessage.classList.add('hidden');
        loader.classList.remove('hidden');
    }
    
    function hideLoader() {
        loader.classList.add('hidden');
    }
    
    function showResult(data) {
        // Set video info
        videoSize.innerHTML = `<i class="fas fa-file"></i> ${data.video_info.size}`;
        videoType.innerHTML = `<i class="fas fa-video"></i> MP4`;
        
        // Set video title
        const urlParts = data.video_url.split('/');
        const filename = urlParts[urlParts.length - 1].split('?')[0];
        const title = decodeURIComponent(filename.replace(/\+/g, ' ').replace(/\.mp4$/, ''));
        videoTitle.textContent = title || 'Pinterest Video';
        
        // Set download link and make it visible
        downloadLink.href = data.video_url;
        downloadLink.setAttribute('download', filename);
        downloadLink.style.display = 'inline-flex';
        
        // Set video thumbnail
        if (data.thumbnail_url) {
            videoThumbnail.src = data.thumbnail_url;
            videoThumbnail.onerror = function() {
                this.src = '/static/img/video-placeholder.jpg';
            };
        } else {
            videoThumbnail.src = '/static/img/video-placeholder.jpg';
        }
        
        // Show result section
        result.classList.remove('hidden');
        
        // Add click event to thumbnail to preview video
        document.querySelector('.thumbnail-container').addEventListener('click', function() {
            window.open(data.video_url, '_blank');
        });
        
        // Display the video URL in a small text below for debugging
        const urlDisplay = document.createElement('div');
        urlDisplay.className = 'video-url-display';
        urlDisplay.innerHTML = `<small>Video URL: <a href="${data.video_url}" target="_blank">${data.video_url}</a></small>`;
        result.appendChild(urlDisplay);
    }
    
    function generateThumbnail(videoUrl) {
        // Create a temporary video element to capture thumbnail
        const tempVideo = document.createElement('video');
        tempVideo.crossOrigin = 'anonymous';
        tempVideo.src = videoUrl;
        tempVideo.muted = true;
        tempVideo.style.display = 'none';
        document.body.appendChild(tempVideo);
        
        // Try to get thumbnail at 1 second
        tempVideo.addEventListener('loadeddata', function() {
            setTimeout(function() {
                try {
                    // Create canvas and draw video frame
                    const canvas = document.createElement('canvas');
                    canvas.width = tempVideo.videoWidth;
                    canvas.height = tempVideo.videoHeight;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(tempVideo, 0, 0, canvas.width, canvas.height);
                    
                    // Set thumbnail
                    const thumbnailUrl = canvas.toDataURL('image/jpeg');
                    videoThumbnail.src = thumbnailUrl;
                    
                    // Clean up
                    document.body.removeChild(tempVideo);
                } catch (e) {
                    console.error('Error generating thumbnail:', e);
                    // Use fallback thumbnail
                    videoThumbnail.src = '/static/img/video-placeholder.jpg';
                }
            }, 1000);
            
            // Start playing to get to the frame we want
            tempVideo.play().catch(e => {
                console.error('Error playing video for thumbnail:', e);
                // Use fallback thumbnail
                videoThumbnail.src = '/static/img/video-placeholder.jpg';
                document.body.removeChild(tempVideo);
            });
        });
        
        // Handle errors
        tempVideo.addEventListener('error', function() {
            console.error('Error loading video for thumbnail');
            // Use fallback thumbnail
            videoThumbnail.src = '/static/img/video-placeholder.jpg';
            document.body.removeChild(tempVideo);
        });
    }
    
    function showError(message) {
        errorText.textContent = message;
        errorMessage.classList.remove('hidden');
        downloadForm.classList.add('hidden');
        result.classList.add('hidden');
    }
    
    function resetForm() {
        downloadForm.classList.remove('hidden');
        result.classList.add('hidden');
        errorMessage.classList.add('hidden');
        pinterestUrlInput.value = '';
        pinterestUrlInput.focus();
    }
    
    // Add input animation
    pinterestUrlInput.addEventListener('focus', function() {
        this.parentElement.classList.add('focused');
    });
    
    pinterestUrlInput.addEventListener('blur', function() {
        this.parentElement.classList.remove('focused');
    });
    
    // Add placeholder image for video thumbnail
    videoThumbnail.src = '/static/img/video-placeholder.jpg';
});
