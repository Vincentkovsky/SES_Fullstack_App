import { defineComponent, onMounted, ref } from "vue";
import { ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import mapboxgl from "mapbox-gl";
import { TileLayer } from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
export default defineComponent({
    name: "DeckGlMap",
    setup() {
        const mapContainer = ref(null);
        onMounted(() => {
            if (!mapContainer.value)
                return;
            // Set your Mapbox token
            const MAPBOX_ACCESS_TOKEN = "pk.eyJ1IjoidmluY2VudDEyOCIsImEiOiJjbHo4ZHhtcWswMXh0MnBvbW5vM2o0d2djIn0.Qj9VErbIh7yNL-DjTnAUFA";
            // Initialize the Mapbox map
            mapboxgl.accessToken = MAPBOX_ACCESS_TOKEN;
            const map = new mapboxgl.Map({
                container: mapContainer.value, // Container element
                style: "mapbox://styles/mapbox/light-v10", // Mapbox style
                center: [-122.45, 37.78], // Longitude, Latitude
                zoom: 12,
            });
            // Create a Deck.gl layer
            const scatterplotLayer = new ScatterplotLayer({
                id: "scatterplot-layer",
                data: [
                    { position: [-122.45, 37.78], size: 100 },
                    { position: [-122.46, 37.76], size: 200 },
                ],
                getPosition: (d) => d.position,
                getRadius: (d) => d.size,
                getFillColor: [255, 0, 0, 128],
            });
            const layer = new TileLayer({
                id: 'TileLayer',
                data: 'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
                maxZoom: 19,
                minZoom: 0,
                renderSubLayers: props => {
                    const { boundingBox } = props.tile;
                    return new BitmapLayer(props, {
                        data: null,
                        image: props.data,
                        bounds: [boundingBox[0][0], boundingBox[0][1], boundingBox[1][0], boundingBox[1][1]]
                    });
                },
                pickable: true
            });
            // Add Deck.gl to Mapbox
            const deckOverlay = new MapboxOverlay({
                layers: [scatterplotLayer],
            });
            map.addControl(deckOverlay);
        });
        return {
            mapContainer,
        };
    },
});
; /* PartiallyEnd: #3632/script.vue */
function __VLS_template() {
    const __VLS_ctx = {};
    const __VLS_localComponents = {
        ...{},
        ...{},
        ...__VLS_ctx,
    };
    let __VLS_components;
    const __VLS_localDirectives = {
        ...{},
        ...__VLS_ctx,
    };
    let __VLS_directives;
    let __VLS_styleScopedClasses;
    // CSS variable injection 
    // CSS variable injection end 
    let __VLS_resolvedLocalAndGlobalComponents;
    __VLS_elementAsFunction(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({ ref: ("mapContainer"), ...{ style: ({}) }, });
    // @ts-ignore navigation for `const mapContainer = ref()`
    __VLS_ctx.mapContainer;
    var __VLS_slots;
    var __VLS_inheritedAttrs;
    const __VLS_refs = {
        "mapContainer": __VLS_nativeElements['div'],
    };
    var $refs;
    var $el;
    return {
        attrs: {},
        slots: __VLS_slots,
        refs: $refs,
        rootEl: $el,
    };
}
;
let __VLS_self;
