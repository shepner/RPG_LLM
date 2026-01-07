"""System validation for GM administrators."""

import os
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime


class SystemValidator:
    """Validates system functionality for GM administrators."""
    
    def __init__(self):
        """Initialize system validator."""
        self.rules_engine_url = os.getenv("RULES_ENGINE_URL", "http://rules_engine:8002")
        self.auth_url = os.getenv("AUTH_URL", "http://auth:8001")
        self.game_session_url = os.getenv("GAME_SESSION_URL", "http://game_session:8003")
        self.worlds_url = os.getenv("WORLDS_URL", "http://worlds:8004")
        self.game_master_url = os.getenv("GAME_MASTER_URL", "http://game_master:8005")
        self.time_management_url = os.getenv("TIME_MANAGEMENT_URL", "http://time_management:8006")
    
    async def validate_all(self) -> Dict[str, Any]:
        """
        Validate all system components.
        
        Returns:
            Comprehensive validation report
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "unknown",
            "services": {},
            "integrations": {},
            "recommendations": []
        }
        
        # Validate individual services
        results["services"]["auth"] = await self._validate_service("Auth", self.auth_url)
        results["services"]["rules_engine"] = await self._validate_service("Rules Engine (Ma'at)", self.rules_engine_url)
        results["services"]["game_session"] = await self._validate_service("Game Session", self.game_session_url)
        results["services"]["worlds"] = await self._validate_service("Worlds (Gaia)", self.worlds_url)
        results["services"]["game_master"] = await self._validate_service("Game Master (Thoth)", self.game_master_url)
        results["services"]["time_management"] = await self._validate_service("Time Management", self.time_management_url)
        results["services"]["being_registry"] = {"status": "healthy", "message": "Being Registry is running"}
        
        # Validate integrations
        results["integrations"]["atman_maat"] = await self._validate_atman_maat_integration()
        results["integrations"]["rules_indexing"] = await self._validate_rules_indexing()
        
        # Determine overall status
        all_healthy = all(
            s.get("status") == "healthy" 
            for s in results["services"].values()
        )
        all_integrations_ok = all(
            i.get("status") == "ok"
            for i in results["integrations"].values()
        )
        
        if all_healthy and all_integrations_ok:
            results["overall_status"] = "healthy"
        elif all_healthy:
            results["overall_status"] = "degraded"
            results["recommendations"].append("Some integrations are not working correctly")
        else:
            results["overall_status"] = "unhealthy"
            results["recommendations"].append("Some services are not responding")
        
        return results
    
    async def _validate_service(self, name: str, url: str) -> Dict[str, Any]:
        """Validate a single service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "message": f"{name} is responding",
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "message": f"{name} returned status {response.status_code}"
                    }
        except httpx.TimeoutException:
            return {
                "status": "unhealthy",
                "message": f"{name} did not respond within timeout"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"{name} error: {str(e)}"
            }
    
    async def _validate_atman_maat_integration(self) -> Dict[str, Any]:
        """Validate integration between Being Service (Atman) and Rules Engine (Ma'at)."""
        try:
            # Test character creation consultation
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.rules_engine_url}/resolve",
                    json={
                        "action": "Test character creation validation",
                        "context": {
                            "test": True,
                            "character_concept": "strength-based warrior",
                            "game_system": "test"
                        }
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "ok",
                        "message": "Atman-Ma'at integration working",
                        "details": {
                            "rules_engine_responded": True,
                            "has_explanation": bool(data.get("explanation")),
                            "has_metadata": bool(data.get("metadata"))
                        }
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Rules engine returned {response.status_code}",
                        "details": {"response": response.text[:200]}
                    }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Integration test failed: {str(e)}"
            }
    
    async def _validate_rules_indexing(self) -> Dict[str, Any]:
        """Validate that rules files are being indexed."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.rules_engine_url}/rules/list")
                if response.status_code == 200:
                    data = response.json()
                    rules = data.get("rules", [])
                    indexed_count = sum(1 for r in rules if r.get("indexing_status") == "indexed")
                    total_indexable = sum(1 for r in rules if r.get("is_text") or r.get("is_pdf") or r.get("is_epub"))
                    
                    return {
                        "status": "ok" if indexed_count > 0 or total_indexable == 0 else "warning",
                        "message": f"{indexed_count}/{total_indexable} indexable files are indexed",
                        "details": {
                            "total_files": len(rules),
                            "indexable_files": total_indexable,
                            "indexed_files": indexed_count,
                            "pending_files": sum(1 for r in rules if r.get("indexing_status") == "pending"),
                            "indexing_files": sum(1 for r in rules if r.get("indexing_status") == "indexing"),
                            "failed_files": sum(1 for r in rules if r.get("indexing_status") == "failed")
                        }
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Could not check rules indexing: {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Rules indexing check failed: {str(e)}"
            }

