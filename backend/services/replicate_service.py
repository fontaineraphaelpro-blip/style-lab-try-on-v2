"""
Replicate Service
=================
Service pour interagir avec l'API Replicate (génération de try-on).
"""

import io
import replicate
from typing import Union

MODEL_ID = "cuuupid/idm-vton:0513734a452173b8173e907e3a59d19a36266e55b48528559432bd21c7d7e985"


class ReplicateService:
    """Service pour générer des virtual try-ons via Replicate"""
    
    @staticmethod
    def generate_tryon(
        person_image: Union[io.BytesIO, str],
        garment_image: Union[io.BytesIO, str],
        category: str = "upper_body"
    ) -> str:
        """
        Génère un virtual try-on.
        
        Args:
            person_image: Image de la personne (BytesIO ou URL)
            garment_image: Image du vêtement (BytesIO ou URL)
            category: Catégorie (upper_body, lower_body, dresses)
            
        Returns:
            URL de l'image résultat
            
        Raises:
            Exception: Si la génération échoue
        """
        try:
            output = replicate.run(
                MODEL_ID,
                input={
                    "human_img": person_image,
                    "garm_img": garment_image,
                    "garment_des": category,
                    "category": "upper_body"
                }
            )
            
            # Replicate peut retourner une liste ou une string
            result_url = str(output[0]) if isinstance(output, list) else str(output)
            
            return result_url
            
        except Exception as e:
            raise Exception(f"Replicate generation failed: {str(e)}")
    
    @staticmethod
    def validate_image_size(image_bytes: bytes, max_size_mb: int = 10) -> bool:
        """
        Valide la taille d'une image.
        
        Args:
            image_bytes: Bytes de l'image
            max_size_mb: Taille maximum en MB
            
        Returns:
            True si valide, False sinon
        """
        size_mb = len(image_bytes) / (1024 * 1024)
        return size_mb <= max_size_mb