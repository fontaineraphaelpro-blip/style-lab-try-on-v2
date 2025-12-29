/**
 * Try-On Service
 * ===============
 * Service pour générer des virtual try-ons via Replicate API.
 * 
 * INTÉGRATION DANS LE TEMPLATE :
 * - Ce module est appelé depuis les routes API (/api/generate)
 * - Ne modifie PAS le flow OAuth/tokens du template
 */

import Replicate from "replicate";

const REPLICATE_API_TOKEN = process.env.REPLICATE_API_TOKEN;
const MODEL_ID = "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985";

const replicate = new Replicate({
  auth: REPLICATE_API_TOKEN,
});

/**
 * Génère un virtual try-on
 * @param {string|Buffer} personImage - Image de la personne (URL ou Buffer)
 * @param {string|Buffer} garmentImage - Image du vêtement (URL ou Buffer)
 * @param {string} category - Catégorie (upper_body, lower_body, dresses)
 * @returns {Promise<string>} URL de l'image résultat
 */
export async function generateTryOn(personImage, garmentImage, category = "upper_body") {
  try {
    const output = await replicate.run(MODEL_ID, {
      input: {
        human_img: personImage,
        garm_img: garmentImage,
        garment_des: category,
        category: "upper_body",
      },
    });

    // Replicate peut retourner une liste ou une string
    const resultUrl = Array.isArray(output) ? output[0] : output;
    return String(resultUrl);
  } catch (error) {
    throw new Error(`Replicate generation failed: ${error.message}`);
  }
}

/**
 * Valide la taille d'une image
 * @param {number} sizeBytes - Taille en bytes
 * @param {number} maxSizeMB - Taille maximum en MB
 * @returns {boolean}
 */
export function validateImageSize(sizeBytes, maxSizeMB = 10) {
  const sizeMB = sizeBytes / (1024 * 1024);
  return sizeMB <= maxSizeMB;
}

