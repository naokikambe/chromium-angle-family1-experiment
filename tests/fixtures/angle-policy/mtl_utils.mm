bool SupportsMacGPUFamily(id<MTLDevice> device, uint8_t macFamily)
{
#if TARGET_OS_MACCATALYST
#  if __IPHONE_OS_VERSION_MIN_REQUIRED < 160000
    if (macFamily == 1)
    {
        return [device supportsFamily:MTLGPUFamilyMacCatalyst1];
    }
    return [device supportsFamily:MTLGPUFamilyMacCatalyst2];
#  else
    if (macFamily == 1)
    {
        return [device supportsFamily:MTLGPUFamilyMac2];
    }
#  endif
#elif TARGET_OS_OSX && __MAC_OS_X_VERSION_MIN_REQUIRED < 130000
    if (macFamily == 1)
    {
        return [device supportsFamily:MTLGPUFamilyMac1];
    }
#elif TARGET_OS_OSX
    if (macFamily == 1)
    {
        return angle::GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") == "1" &&
               ([device supportsFamily:MTLGPUFamilyMac1] ||
                [device supportsFamily:MTLGPUFamilyMac2]);
    }
#endif
    return [device supportsFamily:MTLGPUFamilyMac2];
}

#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 150000 || \
    __IPHONE_OS_VERSION_MAX_ALLOWED >= 180000 || \
    __TV_OS_VERSION_MAX_ALLOWED >= 180000 || TARGET_OS_VISION
static bool UseLegacyMathOptionsForPhase5Family1(id<MTLDevice> metalDevice,
                                                 MTLCompileOptions *options)
{
    return angle::GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") != "1"
                   ? false
                   : TARGET_OS_OSX && !TARGET_OS_MACCATALYST &&
                     [metalDevice supportsFamily:MTLGPUFamilyMac1] &&
           ![metalDevice supportsFamily:MTLGPUFamilyMac2] &&
           (![options respondsToSelector:@selector(setMathMode:)] ||
            ![options respondsToSelector:@selector(setMathFloatingPointFunctions:)]);
}
#endif

void CreateShaderLibrary(Device *metalDevice, auto options, bool disableFastMath)
{
    if (@available(macOS 15.0, iOS 18.0, *))
    {
        if (UseLegacyMathOptionsForPhase5Family1(metalDevice, options.get()))
        {
            options.get().fastMathEnabled = !disableFastMath;
        }
        else
        {
            if (disableFastMath)
            {
                options.get().mathMode = MTLMathModeSafe;
                options.get().mathFloatingPointFunctions = MTLMathFloatingPointFunctionsPrecise;
            }
            else
            {
                options.get().mathMode = MTLMathModeFast;
                options.get().mathFloatingPointFunctions = MTLMathFloatingPointFunctionsFast;
            }
        }
    }
}
