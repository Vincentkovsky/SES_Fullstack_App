export const fetchTilesList = async () => {
    const response = await fetch("http://localhost:3000/api/tilesList");
    return response.json();
};
export const fetchTileByCoordinates = async (timestamp, z, x, y) => {
    const url = `http://localhost:3000/api/tiles/${timestamp}/${z}/${x}/${y}`; // Replace with your API URL
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch tile: ${response.statusText}`);
        }
        return await response.blob(); // Return the tile as a Blob
    }
    catch (error) {
        console.error("Error fetching tile:", error);
        throw error; // Rethrow the error for handling by the caller
    }
};

export const runInference = async () => {
    const response = await fetch('http://localhost:3000/api/run-inference', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Inference failed');
    }

    return response.json();
};
