CHAT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Product Chat</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        #chat-container { border: 1px solid #ddd; border-radius: 8px; padding: 20px; background: #f9f9f9; }
        #question { width: 70%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; }
        #submit { padding: 10px 20px; font-size: 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        #submit:hover { background: #0056b3; }
        #response { margin-top: 20px; padding: 15px; background: white; border: 1px solid #ddd; border-radius: 4px; min-height: 100px; white-space: pre-wrap; }
        .loading { color: #999; font-style: italic; }
    </style>
</head>
<body>
    <h1>Product Chat Assistant</h1>
    <div id="chat-container">
        <input type="text" id="question" placeholder="Ask about our industrial products..." />
        <button id="submit">Ask</button>
        <div id="response"></div>
    </div>

    <script>
        const questionInput = document.getElementById('question');
        const submitBtn = document.getElementById('submit');
        const responseDiv = document.getElementById('response');

        async function askQuestion() {
            const question = questionInput.value.trim();
            if (!question) return;

            responseDiv.textContent = 'Thinking...';
            responseDiv.className = 'loading';

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question })
                });

                const data = await res.json();
                responseDiv.textContent = data.answer;
                responseDiv.className = '';
            } catch (err) {
                responseDiv.textContent = 'Error: ' + err.message;
                responseDiv.className = '';
            }
        }

        submitBtn.addEventListener('click', askQuestion);
        questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') askQuestion();
        });
    </script>
</body>
</html>
"""
