package com.celestarc.furitrainer;

import net.fabricmc.api.ModInitializer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class FuriTrainerMod implements ModInitializer {
	public static final String MOD_ID = "furi-trainer";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

	@Override
	public void onInitialize() {
		LOGGER.info("Furi Trainer Mod initialized!");
	}
}
