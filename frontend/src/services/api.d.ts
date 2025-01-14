export declare const fetchTilesList: () => Promise<{
    message: string[];
}>;
export declare const fetchTileByCoordinates: (timestamp: string, z: number, x: number, y: number) => Promise<Blob>;
