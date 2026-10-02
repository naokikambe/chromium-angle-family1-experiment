#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s BROWSER_STDERR_LOG\n' "$0" >&2
  exit 64
fi

stderr_log=$1
[[ -f "$stderr_log" && ! -L "$stderr_log" ]] || {
  printf 'browser stderr log does not exist or is symlinked: %s\n' "$stderr_log" >&2
  exit 66
}

awk '
function reset_call() {
    config = ""
    version_key = ""
    version_value = ""
    non_version_attributes = ""
    requested_version = ""
    max_supported_version = ""
    validation_enabled = ""
    context_error_attribute_key = ""
    context_error_attribute_value = ""
    context_initialize_error_code = ""
    context_initialize_error_id = ""
    context_initialize_succeeded = 0
    context_rejected = 0
    context_result = ""
}

function append_unique_key(list, key) {
    if (list == "")
        return key
    if (index(";" list ";", ";" key ";"))
        return list
    return list ";" key
}

function finish_call() {
    if (!in_call)
        return

    context_call_count++
    if (config == "no_config")
        no_config_count++
    else if (config == "selected")
        selected_config_count++

    if (version_key == "0x3098" && version_value == "3") {
        es3_call_count++
        if (es3_non_version_attributes == "")
            es3_non_version_attributes = non_version_attributes
        else if (es3_non_version_attributes != non_version_attributes)
            es3_attributes_consistent = 0
    }
    if (version_key == "0x3098" && version_value == "2") {
        es2_call_count++
        if (es2_non_version_attributes == "")
            es2_non_version_attributes = non_version_attributes
        else if (es2_non_version_attributes != non_version_attributes)
            es2_attributes_consistent = 0
    }

    if (context_rejected)
        context_version_rejection_count++
    if (context_result == "eglCreateContext_return_no_context")
        no_context_count++
    else if (context_result == "eglCreateContext_return_context")
        context_created_count++

    if (max_supported_version != "") {
        if (first_max_supported_version == "")
            first_max_supported_version = max_supported_version
        else if (first_max_supported_version != max_supported_version)
            max_supported_version_consistent = 0
    }
    in_call = 0
}

BEGIN {
    in_call = 0
    context_call_count = 0
    no_config_count = 0
    selected_config_count = 0
    es3_call_count = 0
    es2_call_count = 0
    es3_attributes_consistent = 1
    es2_attributes_consistent = 1
    context_version_rejection_count = 0
    no_context_count = 0
    context_created_count = 0
    bad_attribute_count = 0
    error_3004_count = 0
    context_validation_enabled_values = ""
    context_error_attribute_keys = ""
    context_error_attribute_values = ""
    context_initialize_error_codes = ""
    context_initialize_error_ids = ""
    context_initialize_success_count = 0
    family1_es3_to_es2_fallback_count = 0
    context_attribute_validation_failure_keys = ""
    context_attribute_value_validation_failure_keys = ""
    first_max_supported_version = ""
    max_supported_version_consistent = 1
    reset_call()
}

{
    if (index($0, "EGL_BAD_ATTRIBUTE"))
        bad_attribute_count++
    if (index($0, "eglGetError_return=0x3004"))
        error_3004_count++

    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] eglCreateContext_enter$/) {
        finish_call()
        reset_call()
        in_call = 1
        next
    }
    if (!in_call)
        next

    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] eglCreateContext_config=/) {
        split($2, field, "=")
        config = field[2]
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] eglCreateContext_attribute /) {
        split($3, key_field, "=")
        split($4, value_field, "=")
        key = key_field[2]
        value = value_field[2]
        if (key == "0x3098") {
            version_key = key
            version_value = value
        } else {
            if (non_version_attributes != "")
                non_version_attributes = non_version_attributes ";"
            non_version_attributes = non_version_attributes key "=" value
        }
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_version_check /) {
        split($3, requested_field, "=")
        split($4, max_field, "=")
        requested_version = requested_field[2]
        max_supported_version = max_field[2]
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] eglCreateContext_validation_enabled=/) {
        split($2, enabled_field, "=")
        validation_enabled = enabled_field[2]
        context_validation_enabled_values = append_unique_key(context_validation_enabled_values,
                                                              validation_enabled)
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_version_rejected /) {
        context_rejected = 1
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_error /) {
        split($3, code_field, "=")
        split($4, key_field, "=")
        split($5, value_field, "=")
        if (code_field[2] == "EGL_BAD_ATTRIBUTE") {
            context_error_attribute_key = key_field[2]
            context_error_attribute_value = value_field[2]
            context_error_attribute_keys = append_unique_key(context_error_attribute_keys,
                                                             context_error_attribute_key)
            context_error_attribute_values = append_unique_key(context_error_attribute_values,
                                                               context_error_attribute_value)
        }
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_initialize_error /) {
        split($3, code_field, "=")
        split($4, id_field, "=")
        context_initialize_error_code = code_field[2]
        context_initialize_error_id = id_field[2]
        context_initialize_error_codes = append_unique_key(context_initialize_error_codes,
                                                           context_initialize_error_code)
        context_initialize_error_ids = append_unique_key(context_initialize_error_ids,
                                                         context_initialize_error_id)
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_initialize_success$/) {
        context_initialize_succeeded = 1
        context_initialize_success_count++
        next
    }
    if (index($0, "[ANGLE_PHASE5_EGL] family1_es3_to_es2_fallback ")) {
        family1_es3_to_es2_fallback_count++
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_attribute_validation /) {
        split($3, key_field, "=")
        split($4, result_field, "=")
        if (result_field[2] == "false")
            context_attribute_validation_failure_keys = append_unique_key(context_attribute_validation_failure_keys, key_field[2])
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] context_attribute_value_validation /) {
        split($3, key_field, "=")
        split($4, value_field, "=")
        split($5, result_field, "=")
        if (result_field[2] == "false")
            context_attribute_value_validation_failure_keys = append_unique_key(context_attribute_value_validation_failure_keys, key_field[2])
        next
    }
    if ($0 ~ /^\[ANGLE_PHASE5_EGL\] eglCreateContext_return_/) {
        context_result = $2
        next
    }
}

END {
    finish_call()
    non_version_attributes_identical = (es3_call_count > 0 && es2_call_count > 0 &&
                                        es3_attributes_consistent && es2_attributes_consistent &&
                                        es3_non_version_attributes == es2_non_version_attributes)
    if (bad_attribute_count > 0 && context_error_attribute_keys != "") {
        conclusion = "egl-bad-attribute-from-context-error-attribute"
    } else if (bad_attribute_count > 0 && context_initialize_error_codes != "") {
        conclusion = "egl-bad-attribute-from-context-initialize-error-needs-key"
    } else if (bad_attribute_count > 0 &&
        (context_attribute_validation_failure_keys != "" ||
         context_attribute_value_validation_failure_keys != "")) {
        conclusion = "egl-bad-attribute-from-context-attribute-validation"
    } else if (bad_attribute_count > 0 && context_version_rejection_count > 0 &&
        non_version_attributes_identical) {
        conclusion = "egl-bad-attribute-from-context-version-rejection"
    } else if (bad_attribute_count > 0 && context_version_rejection_count > 0) {
        conclusion = "egl-bad-attribute-with-context-version-rejection-needs-review"
    } else if (bad_attribute_count > 0) {
        conclusion = "egl-bad-attribute-source-not-context-version"
    } else {
        conclusion = "no-egl-bad-attribute-observed"
    }
    printf "SCHEMA=phase5-context-trace-analysis-v1\n"
    printf "CONTEXT_CALL_COUNT=%d\n", context_call_count
    printf "NO_CONFIG_COUNT=%d\n", no_config_count
    printf "SELECTED_CONFIG_COUNT=%d\n", selected_config_count
    printf "ES3_CALL_COUNT=%d\n", es3_call_count
    printf "ES2_CALL_COUNT=%d\n", es2_call_count
    printf "CONTEXT_CREATED_COUNT=%d\n", context_created_count
    printf "NO_CONTEXT_COUNT=%d\n", no_context_count
    printf "CONTEXT_VERSION_REJECTION_COUNT=%d\n", context_version_rejection_count
    printf "EGL_BAD_ATTRIBUTE_COUNT=%d\n", bad_attribute_count
    printf "EGL_ERROR_3004_COUNT=%d\n", error_3004_count
    printf "CONTEXT_VALIDATION_ENABLED_VALUES=%s\n", context_validation_enabled_values
    printf "CONTEXT_ERROR_ATTRIBUTE_KEYS=%s\n", context_error_attribute_keys
    printf "CONTEXT_ERROR_ATTRIBUTE_VALUES=%s\n", context_error_attribute_values
    printf "CONTEXT_INITIALIZE_ERROR_CODES=%s\n", context_initialize_error_codes
    printf "CONTEXT_INITIALIZE_ERROR_IDS=%s\n", context_initialize_error_ids
    printf "CONTEXT_INITIALIZE_SUCCESS_COUNT=%d\n", context_initialize_success_count
    printf "FAMILY1_ES3_TO_ES2_FALLBACK_COUNT=%d\n", family1_es3_to_es2_fallback_count
    printf "CONTEXT_ATTRIBUTE_VALIDATION_FAILURE_KEYS=%s\n",
           context_attribute_validation_failure_keys
    printf "CONTEXT_ATTRIBUTE_VALUE_VALIDATION_FAILURE_KEYS=%s\n",
           context_attribute_value_validation_failure_keys
    printf "CONTEXT_VERSION_ATTRIBUTE_KEY=%s\n", (version_key == "" ? "unknown" : version_key)
    printf "ES3_CONTEXT_VERSION_VALUE=%s\n", (es3_call_count > 0 ? "3" : "unknown")
    printf "ES2_CONTEXT_VERSION_VALUE=%s\n", (es2_call_count > 0 ? "2" : "unknown")
    printf "MAX_SUPPORTED_VERSION=%s\n", (first_max_supported_version == "" ? "unknown" : first_max_supported_version)
    printf "MAX_SUPPORTED_VERSION_CONSISTENT=%s\n", (max_supported_version_consistent ? "true" : "false")
    printf "NON_VERSION_ATTRIBUTES_IDENTICAL=%s\n", (non_version_attributes_identical ? "true" : "false")
    printf "ES3_NON_VERSION_ATTRIBUTES=%s\n", es3_non_version_attributes
    printf "ES2_NON_VERSION_ATTRIBUTES=%s\n", es2_non_version_attributes
    printf "CONCLUSION=%s\n", conclusion
}
' "$stderr_log"
