// Persist user_id across sessions, reset session_id each tab/page load
const userId = localStorage.getItem('user_id') || (() => {
    const id = crypto.randomUUID();
    localStorage.setItem('user_id', id);
    return id;
})();
const sessionId = sessionStorage.getItem('session_id') || (() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem('session_id', id);
    return id;
})();

async function fetchPicture() {
    try {
        document.getElementById('picture').style = "display:none";
        document.getElementById('loading-meme').style = "display:block";
        document.getElementById('message').innerText = "Generating meme...";
        document.getElementById('message').style = "display:block";

        const response = await fetch('/backend/createPicture', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': userId,
                'X-Session-ID': sessionId,
            },
        });

        if (!response.ok) {
            throw new Error('Failed to fetch picture');
        }

        const blob = await response.blob();
        const imgUrl = URL.createObjectURL(blob);

        document.getElementById('loading-meme').style = "display:none";
        document.getElementById('message').style = "display:none";
        document.getElementById('picture').src = imgUrl;
        document.getElementById('picture').style = "display:block;";
    } catch (error) {
        console.error('Error fetching picture:', error);
        document.getElementById('loading-meme').style = "display:none";
        document.getElementById('picture').style = "display:none;";
        document.getElementById('message').innerText = "There was an error fetching a picture. Please retry.";
        document.getElementById('message').style = "display:block;";
    }
}

document.getElementById('go').addEventListener('click', fetchPicture);
